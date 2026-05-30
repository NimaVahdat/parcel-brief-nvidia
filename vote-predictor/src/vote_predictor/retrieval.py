"""Grounding: build councillor voting profiles and retrieve similar past applications.

The LLM agent does not reason in a vacuum — it is grounded in Toronto's actual record. This
module turns the ingested parquet into (a) per-councillor profiles (historical yes-rate and
lean) and (b) the most similar past applications with their outcomes, both of which are
formatted into the agent's prompt as in-context evidence.
"""

from __future__ import annotations

import functools
import json
import math

import pandas as pd

from vote_predictor import aggregate, config, embeddings
from vote_predictor.features import build_features


def _lean(yes_rate: float) -> str:
    """Label a councillor's development lean from their historical yes-rate.

    Args:
        yes_rate (float): Fraction of recorded development votes that were Yes.

    Returns:
        str: A short human label used in the grounding prompt.
    """
    if yes_rate >= 0.7:
        return "pro-development"
    if yes_rate <= 0.4:
        return "development-cautious"
    return "swing"


def build_councillor_profiles(
    votes: pd.DataFrame | None = None, cache: bool = True
) -> dict[str, dict]:
    """Compute per-councillor profiles from recorded votes.

    Args:
        votes (pandas.DataFrame | None): Votes to profile; read from parquet if None. Pass a
            train-only subset during evaluation to avoid leaking test outcomes.
        cache (bool): When True (and reading from parquet), write the profiles to JSON.

    Returns:
        dict[str, dict]: Map of councillor id -> profile with ``n_votes``, ``yes_rate``,
        ``propensity_logit`` (smoothed), ``lean``, and ``committee``.

    Raises:
        FileNotFoundError: If reading from parquet and the votes file is missing.
    """
    if votes is None:
        if not config.VOTES_PARQUET.exists():
            raise FileNotFoundError(
                f"Missing {config.VOTES_PARQUET}. Run `vote-predictor ingest` first."
            )
        votes = pd.read_parquet(config.VOTES_PARQUET)

    votes = votes.copy()
    votes["is_yes"] = votes["vote"].astype(str).str.strip().str.lower().eq("yes").astype(int)
    global_rate = float(votes["is_yes"].mean()) if len(votes) else 0.5
    smoothing = config.PROPENSITY_SMOOTHING

    profiles: dict[str, dict] = {}
    for councillor_id, group in votes.groupby("councillor_id"):
        n = int(len(group))
        yes = int(group["is_yes"].sum())
        rate = (yes + smoothing * global_rate) / (n + smoothing)
        profiles[str(councillor_id)] = {
            "councillor_id": str(councillor_id),
            "committee": str(group["committee"].mode().iloc[0]) if "committee" in group else "",
            "n_votes": n,
            "yes_rate": round(yes / n, 3) if n else round(global_rate, 3),
            "propensity_logit": round(aggregate.sigmoid_inverse(rate), 4),
            "lean": _lean(yes / n if n else global_rate),
        }

    if cache:
        config.ensure_dirs()
        config.PROFILES_JSON.write_text(json.dumps(profiles, indent=2))
    return profiles


def load_or_build_profiles() -> dict[str, dict]:
    """Load cached councillor profiles, building them if the cache is absent.

    Returns:
        dict[str, dict]: The councillor profiles (empty dict if no votes data exists yet).
    """
    if config.PROFILES_JSON.exists():
        return json.loads(config.PROFILES_JSON.read_text())
    try:
        return build_councillor_profiles()
    except FileNotFoundError:
        return {}


def global_logit(profiles: dict[str, dict]) -> float:
    """The population-level prior logit: the mean councillor propensity, or the default prior.

    The single source of this value, so the agent, panel, and eval all anchor an ungrounded
    councillor to the same prior (they previously inlined this with divergent fallbacks).

    Args:
        profiles (dict[str, dict]): Councillor profiles (possibly empty).

    Returns:
        float: Mean ``propensity_logit`` across profiles, or
        ``sigmoid_inverse(config.DEFAULT_APPROVAL_PRIOR)`` when there are no profiles.
    """
    if not profiles:
        return aggregate.sigmoid_inverse(config.DEFAULT_APPROVAL_PRIOR)
    return sum(p["propensity_logit"] for p in profiles.values()) / len(profiles)


def _case_summary(record: dict) -> str:
    """Render a one-line feature summary for a precedent application.

    Args:
        record (dict): An application row.

    Returns:
        str: A compact "units, height, affordable, variances" summary.
    """
    feats = build_features(record)
    return (
        f"{feats.total_units} units, {feats.height_m:.0f}m, "
        f"{feats.affordable_share:.0%} affordable, {feats.requested_variances_count} variances"
    )


def _query_text(application: dict) -> str:
    """Compose an embedding query string from a Contract-1 application.

    Mirrors the indexed text style (type/address/description) so feature-only inference
    inputs still retrieve sensibly.

    Args:
        application (dict): The application being predicted.

    Returns:
        str: A descriptive query sentence.
    """
    feats = build_features(application)
    return (
        f"{feats.neighborhood} development, {feats.total_units} units, "
        f"{feats.height_m:.0f}m tall, {feats.affordable_share:.0%} affordable, "
        f"{'with' if feats.retail_flag else 'no'} retail, "
        f"{feats.requested_variances_count} variances"
    )


@functools.lru_cache(maxsize=1)
def _embedding_index() -> embeddings.EmbeddingIndex | None:
    """Load (or build and cache) the application embedding index once per process.

    Returns:
        EmbeddingIndex | None: The index, or None if embeddings are unavailable or there is
        no application data to index.
    """
    if not embeddings.is_available():
        return None
    index = embeddings.EmbeddingIndex.load()
    if index is None and config.APPLICATIONS_PARQUET.exists():
        index = embeddings.build_application_index(pd.read_parquet(config.APPLICATIONS_PARQUET))
    return index


def _file_key(path) -> tuple[str, float] | None:
    """Return a cache key (path, mtime) for a parquet file, or None if absent.

    Args:
        path: A parquet file path.

    Returns:
        tuple[str, float] | None: ``(str(path), mtime)`` so the corpus cache invalidates when
        the file is rewritten by a new ingest, or None when the file does not exist.
    """
    return (str(path), path.stat().st_mtime) if path.exists() else None


@functools.lru_cache(maxsize=2)
def _corpus_cached(apps_key, votes_key, recs_key):
    """Load and derive the precedent corpus, cached on the inputs' (path, mtime) keys.

    Args:
        apps_key: ``_file_key`` of the applications parquet (drives cache invalidation).
        votes_key: ``_file_key`` of the votes parquet.
        recs_key: ``_file_key`` of the staff-recs parquet (may be None).

    Returns:
        tuple: ``(apps, outcomes, recs)`` — the application frame, a per-application Yes-rate
        Series, and a recommendation Series. None of these is mutated by callers.
    """
    apps = pd.read_parquet(config.APPLICATIONS_PARQUET)
    votes = pd.read_parquet(config.VOTES_PARQUET)
    if "application_id" in votes:
        votes = votes.dropna(subset=["application_id"])
    is_yes = votes["vote"].astype(str).str.strip().str.lower().eq("yes").astype(int)
    outcomes = is_yes.groupby(votes["application_id"]).mean()
    recs = (
        pd.read_parquet(config.STAFF_RECS_PARQUET).set_index("application_id")["recommendation"]
        if recs_key is not None
        else pd.Series(dtype=str)
    )
    return apps, outcomes, recs


def _corpus():
    """Return the (apps, outcomes, recs) corpus, loaded once per ingest and reused.

    Avoids re-reading three parquet files (and re-deriving outcomes) on every
    ``find_similar_applications`` call — which in the backtest runs once per test item.

    Returns:
        tuple: ``(apps, outcomes, recs)`` from ``_corpus_cached``.
    """
    return _corpus_cached(
        _file_key(config.APPLICATIONS_PARQUET),
        _file_key(config.VOTES_PARQUET),
        _file_key(config.STAFF_RECS_PARQUET),
    )


def find_similar_applications(
    application: dict,
    k: int = config.SIMILAR_CASES_K,
    allowed_ids: set[str] | None = None,
) -> list[dict]:
    """Retrieve the k most similar past applications and their outcomes.

    Uses semantic similarity over real application text via the local nomic-embed-text model
    when the embedding endpoint is reachable, and falls back to a normalized feature-distance
    otherwise. Each case carries its ``application_id`` (the precedent evidence id the panel
    cites), a feature summary, the actual approve/reject outcome, and the staff recommendation.

    Args:
        application (dict): The application being predicted (Contract 1 fields).
        k (int): Number of neighbors to return.
        allowed_ids (set[str] | None): When provided, only these application ids are eligible
            as precedent. The backtest passes the training-period ids so test-period outcomes
            cannot leak into the Reasoner's grounding context.

    Returns:
        list[dict]: Up to k cases with ``application_id``, ``summary``, ``outcome``,
        ``staff_rec``, and ``method``. Empty if no historical data is available.
    """
    if not (config.APPLICATIONS_PARQUET.exists() and config.VOTES_PARQUET.exists()):
        return []

    apps, outcomes, recs = _corpus()

    def _eligible(app_id: str) -> bool:
        """Whether an application id can be returned as precedent (has an outcome and is allowed)."""
        return app_id in outcomes.index and (allowed_ids is None or app_id in allowed_ids)

    def _case(record: dict, app_id: str, method: str) -> dict:
        """Build a precedent case dict with its evidence id and outcome."""
        return {
            "application_id": str(app_id),
            "summary": _case_summary(record),
            "outcome": "approved" if outcomes.get(app_id, 0) > 0.5 else "rejected",
            "staff_rec": str(recs.get(app_id, "unknown")),
            "method": method,
        }

    target_id = str(application.get("parcel_id") or application.get("application_id") or "")
    index = _embedding_index()
    if index is not None:
        apps_by_id = apps.drop_duplicates(subset=["application_id"]).set_index("application_id")
        cases: list[dict] = []
        for app_id, _score in index.query(_query_text(application), k=k * 3, exclude_id=target_id):
            if not _eligible(app_id) or app_id not in apps_by_id.index:
                continue
            cases.append(_case(apps_by_id.loc[app_id].to_dict(), app_id, "embedding"))
            if len(cases) >= k:
                break
        if cases:
            return cases  # else fall through to feature distance

    target = build_features(application)
    scales = {
        "height_m": 50.0,
        "total_units": 200.0,
        "affordable_share": 0.3,
        "variance_count": 5.0,
    }
    scored: list[tuple[float, dict]] = []
    for record in apps.to_dict("records"):
        app_id = record["application_id"]
        if not _eligible(app_id):
            continue
        feats = build_features(record)
        dist = math.sqrt(
            ((target.height_m - feats.height_m) / scales["height_m"]) ** 2
            + ((target.total_units - feats.total_units) / scales["total_units"]) ** 2
            + ((target.affordable_share - feats.affordable_share) / scales["affordable_share"]) ** 2
            + (
                (target.requested_variances_count - feats.requested_variances_count)
                / scales["variance_count"]
            )
            ** 2
        )
        scored.append((dist, _case(record, app_id, "feature_distance")))
    scored.sort(key=lambda item: item[0])
    return [case for _, case in scored[:k]]


def format_context(
    application: dict,
    councillors: list[str],
    profiles: dict[str, dict],
    staff_rec: str,
    similar: list[dict],
) -> str:
    """Format councillor histories, the staff rec, and precedent into a grounding block.

    Args:
        application (dict): The application being predicted.
        councillors (list[str]): Normalized councillor ids on the committee.
        profiles (dict[str, dict]): Councillor profiles from ``load_or_build_profiles``.
        staff_rec (str): The staff recommendation key.
        similar (list[dict]): Similar past cases from ``find_similar_applications``.

    Returns:
        str: A plain-text evidence block to embed in the agent prompt.
    """
    feats = build_features(application)
    lines = [
        "PROJECT:",
        f"  {feats.total_units} units, {feats.height_m:.0f}m tall "
        f"({feats.height_over_ratio:.0%} over as-of-right), "
        f"{feats.affordable_share:.0%} affordable, "
        f"{'has' if feats.retail_flag else 'no'} ground-floor retail, "
        f"{feats.requested_variances_count} requested variances.",
        f"STAFF RECOMMENDATION: {staff_rec}",
        "",
        "COUNCILLORS ON THIS COMMITTEE (historical record):",
    ]
    for cid in councillors:
        prof = profiles.get(cid)
        if prof:
            lines.append(
                f"  - {cid}: {prof['lean']}, voted Yes {prof['yes_rate']:.0%} of "
                f"{prof['n_votes']} recorded development votes."
            )
        else:
            lines.append(f"  - {cid}: no recorded voting history available.")
    if similar:
        lines.append("")
        lines.append("SIMILAR PAST APPLICATIONS (cite the id as evidence):")
        for case in similar:
            ref = case.get("application_id", "?")
            lines.append(
                f"  - [{ref}] {case['summary']} -> {case['outcome']} (staff: {case['staff_rec']})."
            )
    return "\n".join(lines)
