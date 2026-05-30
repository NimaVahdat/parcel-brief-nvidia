"""Evaluation: backtest the panel on a held-out time split, with grounding ablations.

Builds councillor profiles from the **training period only** (so test outcomes never leak
into a councillor's profile), runs each arm on each held-out application, and reports
per-councillor accuracy/AUC/Brier and committee-outcome accuracy (all + contested items).

Arms:
* ``panel`` — the grounded multi-agent panel (the headline; uses the LLM when reachable).
* ``fallback`` — the deterministic record+staff heuristic (no model).
* ``no_grounding`` — an LLM ablation given only the project features (no councillor records,
  no precedent, no staff rec): the comparison that shows grounding moves the needle.
* ``base_rate`` / ``always_yes`` — naive baselines an honest forecaster must beat.

Works offline via the fallback; the LLM arms need a reachable endpoint.
"""

from __future__ import annotations

import logging

import pandas as pd

from vote_predictor import config, panel, retrieval
from vote_predictor.agent import VotePredictorAgent
from vote_predictor.aggregate import poisson_binomial_majority, sigmoid
from vote_predictor.features import build_features
from vote_predictor.normalize import normalize_councillor_id

logger = logging.getLogger(__name__)


def _auc(probs: list[float], labels: list[int]) -> float:
    """Compute ROC AUC via the rank-sum (Mann-Whitney) formula, no sklearn.

    Args:
        probs (list[float]): Predicted Yes-probabilities.
        labels (list[int]): Ground-truth 0/1 labels.

    Returns:
        float: ROC AUC, or 0.5 when only one class is present.
    """
    pos = [i for i, y in enumerate(labels) if y == 1]
    neg = [i for i, y in enumerate(labels) if y == 0]
    if not pos or not neg:
        return 0.5
    order = sorted(range(len(probs)), key=lambda i: probs[i])
    ranks = [0.0] * len(probs)
    i = 0
    while i < len(order):  # average ranks within ties
        j = i
        while j < len(order) and probs[order[j]] == probs[order[i]]:
            j += 1
        avg = (i + j + 1) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg
        i = j
    rank_sum = sum(ranks[i] for i in pos)
    return (rank_sum - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def _brier(probs: list[float], labels: list[int]) -> float:
    """Mean squared error of probabilistic predictions (lower is better).

    Args:
        probs (list[float]): Predicted Yes-probabilities.
        labels (list[int]): Ground-truth 0/1 labels.

    Returns:
        float: The Brier score; 1.0 for empty input.
    """
    if not probs:
        return 1.0
    return sum((p - y) ** 2 for p, y in zip(probs, labels, strict=False)) / len(probs)


def _bare_context(application: dict, councillors: list[str]) -> str:
    """Build a grounding-free context for the no-grounding ablation.

    Args:
        application (dict): The application fields.
        councillors (list[str]): Normalized councillor ids.

    Returns:
        str: A context with the project only — no records, precedent, or staff rec.
    """
    feats = build_features(application)
    return (
        f"PROJECT: {feats.total_units} units, {feats.height_m:.0f}m, "
        f"{feats.affordable_share:.0%} affordable, {feats.requested_variances_count} variances.\n"
        f"COUNCILLORS: {councillors}\n"
        "(No councillor voting history, precedent, or staff recommendation is provided.)"
    )


def _no_grounding_scores(
    application: dict,
    councillors: list[str],
    profiles: dict[str, dict],
    global_logit: float,
) -> dict[str, float]:
    """Score councillors with an LLM that has no grounding context (the ablation arm).

    Routes the bare-context claims through the SAME Skeptic gate the panel arm uses (with no
    precedent), so the only difference between the arms is the grounding context — not the
    gating. This keeps the panel-vs-ablation comparison fair.

    Args:
        application (dict): The application fields.
        councillors (list[str]): Normalized councillor ids.
        profiles (dict[str, dict]): Train-only councillor profiles (for the Skeptic's prior).
        global_logit (float): Mean propensity logit (fallback prior).

    Returns:
        dict[str, float]: Post-Skeptic per-councillor Yes-probabilities.
    """
    claims = panel.run_reasoner_llm(_bare_context(application, councillors), councillors)
    scores: dict[str, float] = {}
    for cid in councillors:
        reasoning = panel.skeptic_review(
            cid, claims.get(cid, {}), profiles.get(cid), set(), {}, "unknown", global_logit
        )
        scores[cid] = reasoning.p_yes
    return scores


def evaluate(
    use_llm: bool | None = None,
    limit: int | None = None,
    ablations: bool = False,
    verify: bool | None = None,
    verify_ablation: bool = False,
) -> dict:
    """Run the backtest and print a report comparing the panel to baselines and ablations.

    Args:
        use_llm (bool | None): Force the panel's LLM path on/off; defaults to ``config.USE_LLM``.
        limit (int | None): Cap the number of test applications (useful when the LLM is on).
        ablations (bool): When True, also run the LLM no-grounding ablation arm.
        verify (bool | None): Force the panel's agentic verification layer on/off; defaults to
            ``config.VERIFY_CLAIMS``. The layer is inert unless the LLM Reasoner also runs.
        verify_ablation (bool): When True, add a ``panel_unverified`` arm (verification off) so
            the report shows directly what the verification layer changes — how much extra
            abstention it introduces and whether committee-outcome accuracy holds.

    Returns:
        dict: A metrics report keyed by arm, plus ``meta`` (including verification-layer stats).

    Raises:
        FileNotFoundError: If the processed data is missing (run ingest first).
    """
    for path in (config.APPLICATIONS_PARQUET, config.VOTES_PARQUET):
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}. Run `vote-predictor ingest` first.")

    apps = pd.read_parquet(config.APPLICATIONS_PARQUET)
    # Parse dates before sorting so the 80/20 split is a true temporal partition rather than a
    # lexicographic accident on non-ISO strings; undated rows sort to the training side.
    apps["application_date"] = pd.to_datetime(apps["application_date"], errors="coerce")
    apps = apps.sort_values("application_date", na_position="first")
    votes = pd.read_parquet(config.VOTES_PARQUET)
    if "application_id" in votes:
        votes = votes.dropna(subset=["application_id"])
    votes["is_yes"] = votes["vote"].astype(str).str.strip().str.lower().eq("yes").astype(int)
    recs = (
        pd.read_parquet(config.STAFF_RECS_PARQUET).set_index("application_id")["recommendation"]
        if config.STAFF_RECS_PARQUET.exists()
        else pd.Series(dtype=str)
    )

    cut = int(len(apps) * 0.8)
    train_ids = set(apps.iloc[:cut]["application_id"])
    test_apps = apps.iloc[cut:]
    if limit:
        test_apps = test_apps.head(limit)

    # Leakage guard: profiles see ONLY training-period votes.
    train_votes = votes[votes["application_id"].isin(train_ids)]
    profiles = retrieval.build_councillor_profiles(votes=train_votes, cache=False)
    global_logit = retrieval.global_logit(profiles)

    panel_agent = VotePredictorAgent(profiles=profiles, use_llm=use_llm, use_verify=verify)
    fallback_agent = VotePredictorAgent(profiles=profiles, use_llm=False)
    unverified_agent = (
        VotePredictorAgent(profiles=profiles, use_llm=use_llm, use_verify=False)
        if verify_ablation
        else None
    )

    arms = ["panel", "fallback", "base_rate", "always_yes"]
    if ablations:
        arms.append("no_grounding")
    if verify_ablation:
        arms.append("panel_unverified")
    probs: dict[str, list[float]] = {arm: [] for arm in arms}
    items: dict[str, list[dict]] = {arm: [] for arm in arms}
    labels: list[int] = []
    panel_abstained = 0
    panel_graded = 0
    verifier_counts = {"verified": 0, "downgraded": 0, "abstained": 0}
    # Group once instead of a full-frame boolean scan per test item.
    votes_by_app = dict(tuple(votes.groupby("application_id")))

    for record in test_apps.to_dict("records"):
        app_id = record["application_id"]
        app_votes = votes_by_app.get(app_id)
        if app_votes is None or app_votes.empty:
            continue
        councillors = [normalize_councillor_id(str(c)) for c in app_votes["councillor_id"]]
        label_by_c = {
            normalize_councillor_id(str(c)): int(y)
            for c, y in zip(app_votes["councillor_id"], app_votes["is_yes"], strict=False)
        }
        ward = record.get("ward_councillor_id")
        ward_norm = normalize_councillor_id(str(ward)) if ward else None
        staff_rec = str(recs.get(app_id, "unknown"))

        # Panel arm: restrict precedent to TRAIN ids so test outcomes cannot leak into the
        # Reasoner's context, and capture the trace to measure how often the Skeptic abstains.
        panel_pred, panel_trace = panel_agent.predict_with_trace(
            record, councillors, staff_rec, ward_norm, precedent_ids=train_ids
        )
        panel_abstained += panel_trace.n_abstained
        panel_graded += len(panel_trace.councillors)
        verifier_counts["verified"] += panel_trace.n_verified
        verifier_counts["downgraded"] += panel_trace.n_verifier_downgraded
        verifier_counts["abstained"] += panel_trace.n_verifier_abstained
        arm_scores: dict[str, dict[str, float]] = {
            "panel": panel_pred.per_councillor,
            "fallback": fallback_agent.predict(
                record, councillors, staff_rec, ward_norm
            ).per_councillor,
            "base_rate": {
                cid: sigmoid(profiles.get(cid, {}).get("propensity_logit", global_logit))
                for cid in councillors
            },
            "always_yes": {cid: 1.0 for cid in councillors},
        }
        if ablations:
            arm_scores["no_grounding"] = _no_grounding_scores(
                record, councillors, profiles, global_logit
            )
        if unverified_agent is not None:
            arm_scores["panel_unverified"] = unverified_agent.predict(
                record, councillors, staff_rec, ward_norm, precedent_ids=train_ids
            ).per_councillor

        actual_approve = (sum(label_by_c.values()) / len(label_by_c)) > 0.5
        contested = len(set(label_by_c.values())) > 1
        for cid in councillors:
            labels.append(label_by_c[cid])
        for arm in arms:
            for cid in councillors:
                probs[arm].append(arm_scores[arm][cid])
            predicted_approve = poisson_binomial_majority(list(arm_scores[arm].values())) > 0.5
            items[arm].append(
                {
                    "predicted_approve": predicted_approve,
                    "actual_approve": actual_approve,
                    "contested": contested,
                }
            )

    def _metrics(arm: str) -> dict:
        """Compute the metric block for one arm."""
        arm_probs = probs[arm]
        vote_acc = (
            sum(int((p >= 0.5) == bool(y)) for p, y in zip(arm_probs, labels, strict=False))
            / len(labels)
            if labels
            else 0.0
        )
        rows = items[arm]
        contested_rows = [r for r in rows if r["contested"]]
        return {
            "vote_accuracy": round(vote_acc, 4),
            "auc": round(_auc(arm_probs, labels), 4),
            "brier": round(_brier(arm_probs, labels), 4),
            "outcome_accuracy_all": round(
                sum(int(r["predicted_approve"] == r["actual_approve"]) for r in rows) / len(rows), 4
            )
            if rows
            else 0.0,
            "outcome_accuracy_contested": round(
                sum(int(r["predicted_approve"] == r["actual_approve"]) for r in contested_rows)
                / len(contested_rows),
                4,
            )
            if contested_rows
            else 0.0,
        }

    report = {arm: _metrics(arm) for arm in arms}
    abstain_rate = round(panel_abstained / panel_graded, 4) if panel_graded else 0.0
    report["panel"]["abstain_rate"] = abstain_rate
    n_verified_eligible = sum(verifier_counts.values())
    verifier_downgrade_rate = (
        round(verifier_counts["downgraded"] / n_verified_eligible, 4)
        if n_verified_eligible
        else 0.0
    )
    verifier_abstain_rate = (
        round(verifier_counts["abstained"] / n_verified_eligible, 4) if n_verified_eligible else 0.0
    )
    report["panel"]["verifier_downgrade_rate"] = verifier_downgrade_rate
    report["panel"]["verifier_abstain_rate"] = verifier_abstain_rate
    report["meta"] = {
        "mode": "llm" if panel_agent.use_llm else "fallback",
        "n_test_votes": len(labels),
        "n_test_items": len(items["panel"]),
        "panel_abstain_rate": abstain_rate,
        "ablations": ablations,
        "verification_enabled": bool(panel_agent.use_verify and panel_agent.use_llm),
        "n_verifier_eligible": n_verified_eligible,
        "verifier_downgrade_rate": verifier_downgrade_rate,
        "verifier_abstain_rate": verifier_abstain_rate,
    }

    logger.info(
        "=== vote-predictor evaluation (%s mode, held-out time split) ===", report["meta"]["mode"]
    )
    logger.info(
        "test votes=%d items=%d panel_abstain_rate=%s",
        report["meta"]["n_test_votes"],
        report["meta"]["n_test_items"],
        abstain_rate,
    )
    logger.info("%s", f"{'metric':<28}" + "".join(f"{arm:>14}" for arm in arms))
    for metric in (
        "vote_accuracy",
        "auc",
        "brier",
        "outcome_accuracy_all",
        "outcome_accuracy_contested",
    ):
        logger.info("%s", f"{metric:<28}" + "".join(f"{report[arm][metric]:>14}" for arm in arms))
    if abstain_rate > 0.5:
        logger.warning(
            "panel abstained on %.0f%% of councillors — grounding is thin; metrics may track base_rate",
            abstain_rate * 100,
        )
    if report["meta"]["verification_enabled"]:
        logger.info(
            "verification layer: %d gate-passed claims -> downgrade_rate=%s abstain_rate=%s",
            n_verified_eligible,
            verifier_downgrade_rate,
            verifier_abstain_rate,
        )
    return report


def measure_verifier_stability(n_repeats: int = 3, limit: int | None = 20) -> dict:
    """Probe verifier nondeterminism: re-run the verification layer on fixed gate claims K times.

    The verifiers run at temperature 0 with strict-JSON outputs, so at temp 0 their verdicts
    should be identical across repeats. This re-reasons over the *same* gate claims ``n_repeats``
    times and reports the fraction of claims whose verification verdict changed — a flip rate of 0
    is the determinism guarantee a CI gate should assert. The LLM Reasoner runs once per item; only
    the verifier calls repeat, so this isolates verifier nondeterminism from Reasoner variance.

    Args:
        n_repeats (int): How many times to re-run the verification layer on each item (>= 2).
        limit (int | None): Cap the number of test applications probed (the LLM is required).

    Returns:
        dict: ``{"flip_rate", "n_claims", "n_repeats", "n_flipped", "n_items"}``. ``flip_rate`` is
        ``n_flipped / n_claims``; an empty probe (no reachable model / no grounded claims) reports
        a flip rate of 0.0 over 0 claims.

    Raises:
        FileNotFoundError: If the processed data is missing (run ingest first).
    """
    from vote_predictor import verify

    for path in (config.APPLICATIONS_PARQUET, config.VOTES_PARQUET):
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}. Run `vote-predictor ingest` first.")

    apps = pd.read_parquet(config.APPLICATIONS_PARQUET)
    apps["application_date"] = pd.to_datetime(apps["application_date"], errors="coerce")
    apps = apps.sort_values("application_date", na_position="first")
    votes = pd.read_parquet(config.VOTES_PARQUET)
    if "application_id" in votes:
        votes = votes.dropna(subset=["application_id"])
    recs = (
        pd.read_parquet(config.STAFF_RECS_PARQUET).set_index("application_id")["recommendation"]
        if config.STAFF_RECS_PARQUET.exists()
        else pd.Series(dtype=str)
    )

    cut = int(len(apps) * 0.8)
    train_ids = set(apps.iloc[:cut]["application_id"])
    test_apps = apps.iloc[cut:]
    if limit:
        test_apps = test_apps.head(limit)
    train_votes = votes[votes["application_id"].isin(train_ids)]
    profiles = retrieval.build_councillor_profiles(votes=train_votes, cache=False)
    # use_verify=False so predict_with_trace returns the GATE traces, which we then re-verify.
    gate_agent = VotePredictorAgent(profiles=profiles, use_llm=True, use_verify=False)
    votes_by_app = dict(tuple(votes.groupby("application_id")))

    n_claims = 0
    n_flipped = 0
    n_items = 0
    for record in test_apps.to_dict("records"):
        app_votes = votes_by_app.get(record["application_id"])
        if app_votes is None or app_votes.empty:
            continue
        councillors = [normalize_councillor_id(str(c)) for c in app_votes["councillor_id"]]
        staff_rec = str(recs.get(record["application_id"], "unknown"))
        _, gate_trace = gate_agent.predict_with_trace(
            record, councillors, staff_rec, None, precedent_ids=train_ids
        )
        summary = retrieval.case_summary(record)
        runs = [
            {
                cid: outcome.record.verdict
                for cid, outcome in verify.verify_panel(
                    gate_trace.councillors, profiles, staff_rec, summary
                ).items()
            }
            for _ in range(max(2, n_repeats))
        ]
        base = runs[0]
        if not base:
            continue
        n_items += 1
        for cid, verdict in base.items():
            n_claims += 1
            if any(run.get(cid) != verdict for run in runs[1:]):
                n_flipped += 1

    flip_rate = round(n_flipped / n_claims, 4) if n_claims else 0.0
    report = {
        "flip_rate": flip_rate,
        "n_claims": n_claims,
        "n_repeats": max(2, n_repeats),
        "n_flipped": n_flipped,
        "n_items": n_items,
    }
    logger.info(
        "verifier stability: flip_rate=%s over %d claims x %d repeats (%d items)",
        flip_rate,
        n_claims,
        report["n_repeats"],
        n_items,
    )
    if flip_rate > 0:
        logger.warning(
            "verifier verdicts flipped on %.1f%% of claims at temperature 0 — investigate "
            "nondeterminism before trusting the verified panel",
            flip_rate * 100,
        )
    return report


def main() -> None:
    """CLI entry point: ``python -m vote_predictor.eval``.

    Returns:
        None.
    """
    evaluate()


if __name__ == "__main__":
    main()
