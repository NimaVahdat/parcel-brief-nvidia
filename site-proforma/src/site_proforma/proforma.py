"""calculate() — the financial pro-forma contract function."""

from site_proforma.schemas import FinancialModel, Massing, SiteData


# Placeholder Toronto construction cost benchmarks ($/sqft GFA).
# TODO: replace with actual Altus / Hanscomb / city benchmarks per use type.
COST_PER_SQM_BY_USE = {
    "residential": 5300.0,
    "retail": 4200.0,
    "office": 4800.0,
}


def calculate(massing: Massing, site: SiteData) -> FinancialModel:
    """Compute the pro-forma.

    Mock implementation. Replace with:
      1. Construction cost = sum(GFA_by_use × cost_per_sqm_by_use).
      2. Annual rent = sum(units_by_type × CMHC rent for neighborhood × 12).
      3. Debt service at assumed rate (e.g. 6%, 60% LTV).
      4. IRR over 5 and 10 years with terminal cap rate.
      5. Sensitivities: rate ±100bp, stabilization +6mo, rent ±10%.
    """
    cost = massing.total_gfa_m2 * COST_PER_SQM_BY_USE["residential"]
    annual_rent = sum(massing.unit_mix.values()) * 28000  # placeholder
    debt = cost * 0.6 * 0.06

    sens = {
        "rate_+100bp": {"irr_5y": 0.11, "irr_10y": 0.14},
        "rate_-100bp": {"irr_5y": 0.18, "irr_10y": 0.21},
        "rent_-10pct": {"irr_5y": 0.10, "irr_10y": 0.13},
        "rent_+10pct": {"irr_5y": 0.19, "irr_10y": 0.22},
    }

    return FinancialModel(
        construction_cost=cost,
        projected_annual_rent=annual_rent,
        projected_sale_price=None,
        debt_service=debt,
        irr_5y=0.15,
        irr_10y=0.17,
        sensitivities=sens,
    )
