"""Pro-forma assumptions — Toronto benchmarks, all env-overridable.

These are transparent, defensible defaults (construction cost, rents, financing,
cap rate). A user can tune any of them via env vars without touching code. Sources:
Altus/Hanscomb cost benchmarks, CMHC Toronto rental averages, typical Toronto
development financing terms — order-of-magnitude correct for a screening pro-forma.
"""

from __future__ import annotations

import os


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


# --- construction cost ($/m² GFA, hard + soft) ---
HARD_COST_PSM = {
    "residential": _f("SP_HARD_RES_PSM", 4300.0),   # ~$400/sqft
    "retail": _f("SP_HARD_RETAIL_PSM", 3200.0),
}
SOFT_COST_PCT = _f("SP_SOFT_COST_PCT", 0.22)         # soft costs as % of hard
CONTINGENCY_PCT = _f("SP_CONTINGENCY_PCT", 0.05)

# --- rents (monthly $ per unit, Toronto CMHC-level averages) ---
RENT_PER_UNIT_MONTH = {
    "studio": _f("SP_RENT_STUDIO", 1750.0),
    "1br": _f("SP_RENT_1BR", 2300.0),
    "2br": _f("SP_RENT_2BR", 3050.0),
    "3br": _f("SP_RENT_3BR", 3800.0),
}
DEFAULT_RENT_MONTH = _f("SP_RENT_DEFAULT", 2300.0)
AFFORDABLE_RENT_FACTOR = _f("SP_AFFORDABLE_RENT_FACTOR", 0.6)   # affordable = 60% of market
RETAIL_RENT_PSM_YEAR = _f("SP_RETAIL_RENT_PSM_YR", 540.0)       # ~$50/sqft/yr

# --- operating ---
VACANCY = _f("SP_VACANCY", 0.04)
OPEX_RATIO = _f("SP_OPEX_RATIO", 0.33)        # operating expenses as % of EGI

# --- financing / valuation ---
LTC = _f("SP_LTC", 0.60)                      # loan-to-cost
INTEREST_RATE = _f("SP_INTEREST_RATE", 0.062)
CAP_RATE = _f("SP_CAP_RATE", 0.045)           # terminal cap rate
SALE_PRICE_PSM = _f("SP_SALE_PRICE_PSM", 12000.0)   # condo ~$1115/sqft sellable
SELLABLE_EFFICIENCY = _f("SP_SELLABLE_EFFICIENCY", 0.82)  # sellable / GFA

# --- timing (months) ---
CONSTRUCTION_MONTHS = int(os.getenv("SP_CONSTRUCTION_MONTHS", "24"))
LEASEUP_MONTHS = int(os.getenv("SP_LEASEUP_MONTHS", "12"))

SQFT_PER_SQM = 10.7639
