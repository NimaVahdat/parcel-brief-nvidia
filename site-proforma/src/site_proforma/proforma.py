"""calculate() — the financial pro-forma contract function.

A transparent, deterministic DCF for early-stage screening:

  construction cost  = GFA x cost/m² (hard + soft + contingency)
  stabilized NOI     = (gross rent x (1-vacancy) + retail) x (1 - opex)
  stabilized value   = NOI / cap rate
  IRR (5y, 10y)      = unlevered-to-equity cash flows: equity out, then
                       (NOI - debt service) per year, sale at the horizon
  sensitivities      = rate ±100bp, rent ±10%, +6mo stabilization

All assumptions live in assumptions.py (env-overridable). Numbers are
order-of-magnitude Toronto benchmarks — decision-grade for a screening brief.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from site_proforma import assumptions as A
from site_proforma.schemas import FinancialModel, Massing, SiteData


@dataclass
class _Inputs:
    construction_cost: float
    loan: float
    equity: float
    gross_annual_rent: float
    construction_years: int


def _irr(cashflows: list[float]) -> float:
    """Internal rate of return via bisection. Returns NaN-safe float."""
    def npv(rate: float) -> float:
        return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))

    lo, hi = -0.95, 2.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:  # no sign change in range
        return 0.0 if f_hi > 0 else -0.95
    for _ in range(100):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1.0:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def _noi(gross_annual_rent: float, rent_factor: float) -> float:
    egi = gross_annual_rent * rent_factor * (1.0 - A.VACANCY)
    return egi * (1.0 - A.OPEX_RATIO)


def _irrs(inp: _Inputs, *, interest: float, cap: float, rent_factor: float,
          extra_months: float = 0.0) -> tuple[float, float]:
    """Return (irr_5y, irr_10y) for the given financing/rent assumptions."""
    noi = _noi(inp.gross_annual_rent, rent_factor)
    debt_service = inp.loan * interest
    stabilize_year = inp.construction_years + (1 if extra_months >= 6 else 0)

    g = A.ANNUAL_GROWTH

    def irr_for_horizon(h: int) -> float:
        cfs = [-inp.equity]
        for y in range(1, h + 1):
            if y >= stabilize_year:
                noi_y = noi * (1 + g) ** (y - stabilize_year)
                cf = noi_y - debt_service
            else:
                cf = 0.0
            if y == h:
                # exit on next-year forward NOI capitalized, repay the loan
                exit_noi = noi * (1 + g) ** (h - stabilize_year + 1)
                cf += (exit_noi / cap if cap else 0.0) - inp.loan
            cfs.append(cf)
        return round(_irr(cfs), 4)

    return irr_for_horizon(5), irr_for_horizon(10)


def _gross_annual_rent(massing: Massing) -> float:
    market_units = max(0, sum(massing.unit_mix.values()) - massing.affordable_units)
    # average market rent weighted by the unit mix
    total_units = sum(massing.unit_mix.values()) or 1
    weighted_month = sum(
        n * A.RENT_PER_UNIT_MONTH.get(k, A.DEFAULT_RENT_MONTH)
        for k, n in massing.unit_mix.items()
    ) / total_units
    market_annual = market_units * weighted_month * 12
    affordable_annual = massing.affordable_units * weighted_month * A.AFFORDABLE_RENT_FACTOR * 12
    retail_m2 = massing.retail_sqft / A.SQFT_PER_SQM
    retail_annual = retail_m2 * A.RETAIL_RENT_PSM_YEAR
    return market_annual + affordable_annual + retail_annual


def calculate(massing: Massing, site: SiteData) -> FinancialModel:
    """Compute construction cost, rents, debt service, IRR (5y/10y), sensitivities."""
    retail_m2 = massing.retail_sqft / A.SQFT_PER_SQM
    res_m2 = max(0.0, massing.total_gfa_m2 - retail_m2)
    hard = res_m2 * A.HARD_COST_PSM["residential"] + retail_m2 * A.HARD_COST_PSM["retail"]
    cost = hard * (1 + A.SOFT_COST_PCT) * (1 + A.CONTINGENCY_PCT)
    loan = cost * A.LTC
    equity = cost - loan

    gross_rent = _gross_annual_rent(massing)
    construction_years = math.ceil((A.CONSTRUCTION_MONTHS + A.LEASEUP_MONTHS) / 12)
    inp = _Inputs(cost, loan, equity, gross_rent, construction_years)

    irr5, irr10 = _irrs(inp, interest=A.INTEREST_RATE, cap=A.CAP_RATE, rent_factor=1.0)

    sellable_m2 = res_m2 * A.SELLABLE_EFFICIENCY
    sale_price = sellable_m2 * A.SALE_PRICE_PSM

    def sens(**kw) -> dict[str, float]:
        a, b = _irrs(inp, interest=kw.get("interest", A.INTEREST_RATE),
                     cap=kw.get("cap", A.CAP_RATE),
                     rent_factor=kw.get("rent_factor", 1.0),
                     extra_months=kw.get("extra_months", 0.0))
        return {"irr_5y": a, "irr_10y": b}

    sensitivities = {
        "rate_+100bp": sens(interest=A.INTEREST_RATE + 0.01, cap=A.CAP_RATE + 0.01),
        "rate_-100bp": sens(interest=A.INTEREST_RATE - 0.01, cap=A.CAP_RATE - 0.01),
        "rent_-10pct": sens(rent_factor=0.9),
        "rent_+10pct": sens(rent_factor=1.1),
        "stabilization_+6mo": sens(extra_months=6),
    }

    return FinancialModel(
        construction_cost=round(cost, 0),
        projected_annual_rent=round(gross_rent, 0),
        projected_sale_price=round(sale_price, 0),
        debt_service=round(loan * A.INTEREST_RATE, 0),
        irr_5y=irr5,
        irr_10y=irr10,
        sensitivities=sensitivities,
    )
