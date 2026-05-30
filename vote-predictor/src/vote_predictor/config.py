"""Configuration: data locations, source URLs, and agent settings.

Single place for the constants the rest of the component reads, so dataset ids, file
paths, and tuned thresholds are not scattered as magic values across modules. All paths
resolve relative to a configurable data root (default ``./data``), which stays gitignored.

The local-model settings are read at import time from the environment, with a ``.env`` at
the repo root loaded automatically. The canonical deployment is **nemotron-3-super served
by Ollama** on the GB10 over Tailscale (OpenAI-compatible API at ``:11434/v1``); a vLLM
FP8 endpoint is a supported stricter-JSON fallback. Reads BOTH the project-wide
``LLM_BASE_URL`` / ``LLM_MODEL`` names (used by ``.env`` and the other components) and the
component-specific ``VOTE_PREDICTOR_*`` overrides, so the real endpoint is actually reached
rather than silently falling back to a default.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path


def _load_dotenv() -> None:
    """Load the repo-root ``.env`` into ``os.environ`` if python-dotenv is available.

    Walks up from this file to the first ancestor containing a ``.env`` and loads it
    without overriding variables already set in the real environment, so an explicit
    shell export still wins. A no-op when python-dotenv is not installed.

    Returns:
        None. Side effect only: populates ``os.environ`` from ``.env``.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dotenv is a declared dependency
        return
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.exists():
            load_dotenv(candidate, override=False)
            return


_load_dotenv()


def _env(*names: str, default: str) -> str:
    """Return the first set environment variable among ``names``, else ``default``.

    Lets a single setting be supplied under either the project-wide name (e.g.
    ``LLM_BASE_URL``) or a component-specific override (``VOTE_PREDICTOR_LLM_URL``),
    checked in priority order.

    Args:
        names (str): Environment variable names in descending priority.
        default (str): Value to return when none of the names are set/non-empty.

    Returns:
        str: The resolved value.
    """
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


# --- data layout -----------------------------------------------------------------

#: Root for this component's local data dumps. Override with VOTE_PREDICTOR_DATA_DIR.
COMPONENT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("VOTE_PREDICTOR_DATA_DIR", COMPONENT_ROOT / "data")).resolve()
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

APPLICATIONS_PARQUET = PROCESSED_DIR / "applications.parquet"
VOTES_PARQUET = PROCESSED_DIR / "votes.parquet"
STAFF_RECS_PARQUET = PROCESSED_DIR / "staff_recs.parquet"
CROSSWALK_PARQUET = PROCESSED_DIR / "crosswalk.parquet"
TRAINING_TABLE_PARQUET = PROCESSED_DIR / "labeled_votes.parquet"
PROFILES_JSON = PROCESSED_DIR / "councillor_profiles.json"
EMBEDDINGS_PARQUET = PROCESSED_DIR / "application_embeddings.parquet"

# --- source endpoints (see docs/DATA.md) -----------------------------------------

#: City of Toronto CKAN base — Development Applications (AIC) dataset.
CKAN_BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
CKAN_PACKAGE_SHOW = f"{CKAN_BASE}/api/3/action/package_show"
CKAN_DATASTORE_SEARCH = f"{CKAN_BASE}/api/3/action/datastore_search"
DEVELOPMENT_APPLICATIONS_PACKAGE = "development-applications"

#: The only datastore-active resource on the AIC package (verified live 2026-05-29). The
#: CSV/XML/JSON resources are static dumps (datastore_active=false); datastore_search_sql is
#: disabled, so all dedup/aggregation is done client-side after paging.
AIC_RESOURCE_ID = "8907d8ed-c515-4ce9-b674-9f8c6eefcf0d"
CKAN_DATASTORE_DUMP = f"{CKAN_BASE}/datastore/dump/{AIC_RESOURCE_ID}"
#: Max rows per datastore_search page (full corpus ≈ 3 pages).
CKAN_PAGE_SIZE = 10000

#: TMMIS per-member voting record (Akamai-protected; needs a headless browser).
TMMIS_MEMBER_VOTE_REPORT = (
    "https://app.toronto.ca/tmmis/getAdminReport.do?function=prepareMemberVoteReport"
)
#: The CSV export function the Member Voting Record form posts to (Akamai-gated).
TMMIS_MEMBER_VOTE_CSV = "https://app.toronto.ca/tmmis/getAdminReport.do"
TMMIS_LEGDOCS_BASE = "https://www.toronto.ca/legdocs/mmis"
#: Plain-HTTP (non-Akamai) template for City Planning staff report PDFs.
LEGDOCS_BGRD_TEMPLATE = TMMIS_LEGDOCS_BASE + "/{year}/{body}/bgrd/backgroundfile-{file_id}.pdf"
#: Non-Akamai community mirror of recorded votes — used to seed the backtest label set.
TMMIS_VOTE_MIRROR_BASE = "https://councillors.torontoinsights.com/voting-records"

# --- application-number parsing & joins ------------------------------------------

#: Toronto planning file number: 'YY NNNNNN DDD WW TT' (year, sequence, district, ward, type).
#: Appears verbatim both in the AIC ``APPLICATION#`` column and inside staff-report PDFs as
#: "Planning Application Number", which is the bridge between the two systems.
APPLICATION_NUMBER_RE = r"\b\d{2}\s+\d{6}\s+[A-Z]{3}\s+\d{2}\s+[A-Z]{2}\b"

#: Historical/community district codes -> the current canonical code, applied when
#: normalizing an application number so a staff PDF and the AIC datastore match exactly.
DISTRICT_ALIASES = {
    "TEY": "STE",  # Toronto & East York
    "EYK": "WET",  # Etobicoke York
    "NYK": "NNY",  # North York
    "SCC": "ESC",  # Scarborough
}

#: Application district code -> the component's committee slug.
COMMITTEE_BY_DISTRICT = {
    "STE": "toronto-east-york",
    "NNY": "north-york",
    "ESC": "scarborough",
    "WET": "etobicoke-york",
    "NET": "toronto-east-york",
    "WTE": "toronto-east-york",
}

#: Full TMMIS committee names (as they appear in the Member Voting Record CSV) -> slug.
COMMITTEE_NAME_TO_SLUG = {
    "toronto and east york community council": "toronto-east-york",
    "north york community council": "north-york",
    "scarborough community council": "scarborough",
    "etobicoke york community council": "etobicoke-york",
    "planning and housing committee": "planning-housing",
    "city council": "city-council",
    "executive committee": "executive",
}

#: Motion types (lower-cased) that represent an item's final disposition — the vote we label
#: on, as opposed to amendments/procedural motions.
MAIN_MOTION_TYPES = {"adopt item", "adopt item as amended", "adopt the item", "adopt the balance"}

#: TMMIS agenda-item body code -> committee slug (used to pick the voting roster).
BODY_CODE_TO_COMMITTEE = {
    "TE": "toronto-east-york",
    "NY": "north-york",
    "SC": "scarborough",
    "EY": "etobicoke-york",
    "PH": "planning-housing",
    "CC": "city-council",
    "EX": "executive",
    "MM": "city-council",
}

#: AIC STATUS values that imply a council/committee decision actually happened (so a
#: recorded vote may exist to join). Tribunal (OMB/OLT-prefixed) and in-flight statuses do
#: not, and the predictor abstains on those.
COUNCIL_DECISION_STATUSES = {"Council Approved", "Approved", "Refused"}

#: Council terms post the 2018 25-ward redraw. Pre-2018 votes are excluded because ward
#: boundaries (and therefore councillor rosters) are not comparable.
TERM_WINDOWS: dict[str, tuple[date, date]] = {
    "2018-2022": (date(2018, 12, 1), date(2022, 11, 14)),
    "2022-2026": (date(2022, 11, 15), date(2026, 11, 14)),
}

#: How a joined (application, vote) row was linked — drives down-weighting/abstention.
JOIN_CONFIDENCE_LEVELS = {
    "exact_appnum": "high",
    "address_ward_date": "medium",
    "spatial": "low",
}
#: rapidfuzz token-sort ratio (0-100) above which two normalized addresses are a match.
ADDRESS_FUZZY_THRESHOLD = 88.0
#: Plausible planning lag (months) between an application's submission and its council vote;
#: used to disambiguate fuzzy address matches.
DATE_WINDOW_MONTHS = (3, 36)

# --- agent / grounding settings --------------------------------------------------

#: Laplace smoothing on a councillor's historical yes-rate, so members with few recorded
#: votes fall back toward the global base rate rather than a degenerate 0/1.
PROPENSITY_SMOOTHING = 5.0

#: Minimum recorded votes for a councillor's record to be considered groundable on its own;
#: below this the Skeptic forces an abstain to the smoothed prior. Matches the smoothing.
MIN_GROUNDING_VOTES = 5

#: A per-councillor p_yes this far from a councillor's own prior, with no cited precedent, is
#: treated as over-confident by the Skeptic and pulled back toward the grounded evidence.
OVERCONFIDENCE_DELTA = 0.35

#: Number of similar past applications retrieved as in-context grounding for the agent.
SIMILAR_CASES_K = 5

#: Councillors per Reasoner call. A 123B reasoning model reasoning over a 25-member City
#: Council roster in one call blows the token/latency budget and the JSON truncates; chunking
#: keeps each call bounded (committees of <=8 are one call; full council is a few).
REASONER_BATCH_SIZE = int(os.environ.get("VOTE_PREDICTOR_REASONER_BATCH", "8"))

#: Max Reasoner chunks issued concurrently. Each chunk is an independent LLM call over a
#: disjoint set of councillors merged into one dict, so running them at once changes only the
#: wall-clock, never the result. Cap matches the Ollama server's OLLAMA_NUM_PARALLEL so the
#: chunks actually run in parallel instead of queueing; set to 1 to force the sequential path.
REASONER_MAX_PARALLEL = int(os.environ.get("VOTE_PREDICTOR_REASONER_PARALLEL", "4"))

#: A per-councillor probability within this band of 0.5 is treated as a swing vote.
SWING_BAND = 0.12

#: Approval prior used by the offline fallback before any data exists, so the demo and the
#: connector still return a sensible non-mock answer on a fresh checkout.
DEFAULT_APPROVAL_PRIOR = 0.62

#: Staff-recommendation string -> numeric signal used by the fallback scorer and surfaced
#: to the LLM. Approval is the strongest predictor; refusal the strongest negative.
STAFF_SIGNAL_MAP = {
    "approve": 1.0,
    "approve_with_conditions": 0.6,
    "refuse": -1.0,
    "unknown": 0.0,
}

# --- local LLM (the agent's brain) -----------------------------------------------

#: Local OpenAI-compatible endpoint for the reasoning model on the GB10. Canonical:
#: nemotron-3-super via Ollama (``:11434/v1``); a vLLM FP8 endpoint is a supported fallback.
#: Read at call time so it can be pointed at the Spark without code changes; reads the
#: project-wide ``LLM_BASE_URL`` (set in .env) or the ``VOTE_PREDICTOR_LLM_URL`` override.
LLM_BASE_URL = _env("VOTE_PREDICTOR_LLM_URL", "LLM_BASE_URL", default="http://localhost:11434/v1")
LLM_MODEL = _env("VOTE_PREDICTOR_LLM_MODEL", "LLM_MODEL", default="nemotron-3-super:latest")
#: API key for the local endpoint. Ollama ignores it but the OpenAI client requires a value;
#: honor ``LLM_API_KEY`` from .env so a secured gateway still works.
LLM_API_KEY = _env("VOTE_PREDICTOR_LLM_API_KEY", "LLM_API_KEY", default="local")

#: Request timeout (seconds) for the local LLM endpoint, so a slow or hung server can't
#: block predict() (and the connector) indefinitely. A 123B reasoning model reasoning over a
#: full 5-councillor grounded prompt measures ~40-55s, so the default leaves real headroom.
LLM_TIMEOUT_S = float(os.environ.get("VOTE_PREDICTOR_LLM_TIMEOUT", "120"))

#: Generous completion budget. nemotron-3-super is a reasoning model that streams chain-of-
#: thought into a separate ``reasoning`` field BEFORE writing ``content``; too small a budget
#: starves ``content`` and it comes back empty. See llm_wrapper for the reasoning-safe parse.
REASONING_MAX_TOKENS = int(os.environ.get("VOTE_PREDICTOR_LLM_MAX_TOKENS", "4096"))

#: When False, skip the LLM entirely and use the deterministic offline fallback. Useful for
#: CI and for running the demo without a model server.
USE_LLM = os.environ.get("VOTE_PREDICTOR_USE_LLM", "1") not in ("0", "false", "False")

# --- local embeddings (similar-case retrieval) -----------------------------------

#: Embedding endpoint. nomic-embed-text is served by the same Ollama as the reasoning model,
#: so the embedding base URL defaults to the LLM base URL. (The project-wide ``.env``
#: ``EMBEDDING_MODEL`` names an in-process sentence-transformers model used by other
#: components; this component deliberately uses the Ollama-served ``nomic-embed-text``.)
EMBEDDING_BASE_URL = _env(
    "VOTE_PREDICTOR_EMBEDDING_URL", "EMBEDDING_BASE_URL", default=LLM_BASE_URL
)
EMBEDDING_MODEL = os.environ.get("VOTE_PREDICTOR_EMBEDDING_MODEL", "nomic-embed-text:latest")
#: nomic-embed-text returns 768-dim vectors (verified live).
EMBEDDING_DIM = 768
#: When False, skip embedding retrieval and use the deterministic feature-distance fallback.
USE_EMBEDDINGS = os.environ.get("VOTE_PREDICTOR_USE_EMBEDDINGS", "1") not in ("0", "false", "False")


def ensure_dirs() -> None:
    """Create the local data directories if they do not yet exist.

    Returns:
        None. Side effect only: ``raw`` and ``processed`` dirs are created.
    """
    for path in (RAW_DIR, PROCESSED_DIR):
        path.mkdir(parents=True, exist_ok=True)
