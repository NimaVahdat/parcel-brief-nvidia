# Competitive Analysis — parcel-brief vs. 14 land/zoning/site-intel tools

_Research date: 2026-05-30. Based on parallel investigation of each company's site + web footprint._

## TL;DR

- **Nobody in this set does our two killer features.** Not one of the 14 has **council-vote/approval prediction** or **community-opposition simulation**. That is white space across the entire market.
- **Only two competitors cover Toronto at all:** **LandLogic** (the real threat — Toronto-based, funded, live Teranet feed) and **Zoneomics** (zoning data only). Every other tool is **US-only**. Our Toronto depth is a moat against 12 of 14, but **not** against LandLogic/Zoneomics — against them we must win *above* the zoning layer.
- **Everyone else is one of two things:** (a) a **data/lookup layer** (Regrid, LightBox, LandVision, Land id, Zoneomics) or (b) a **site-screening/feasibility-score SaaS** (SiteScouter, TerraScout, SiteIntel, Civil Intelligence, AtlasIQ, Qlocator, Sitescope, Permitify). We are a **decision engine** that sits on top of both — design + finance + politics + community.

## The competitor landscape

| Company | Toronto? | Category | Real product? | Most threatening feature |
|---|---|---|---|---|
| **LandLogic** | ✅ GTA-verified | Toronto zoning + Multiplex feasibility | ✅ Funded, ~13 ppl, Teranet deal | Multiplex (fourplex viability) + live land-registry data |
| **Zoneomics** | ✅ Toronto data live | Zoning data + API + certified letters | ✅ Real, named clients (Redfin, Moody's) | Owns Toronto zoning data; prospecting filter; API |
| **Regrid** | ⚠️ Parcels only (no CA zoning) | Parcel-boundary data layer | ✅ Esri partner | Nationwide parcel geometry + API |
| **LightBox** | ⚠️ Parcels only (no CA zoning) | CRE data fabric + PZR zoning reports | ✅ Large incumbent | PZR lender-grade zoning due-diligence report |
| **LandVision** | ❌ US-focused | CRE mapping + ML land valuation | ✅ Mature, 4.5★ | Map UX + ML valuation/appreciation forecast |
| **Land id** | ❌ US-only | Land mapping + marketing | ✅ Mature (ex-MapRight) | Shareable/embeddable branded maps, 40+ layers |
| **AtlasIQ** | ❌ US-only | Land-investment "Bloomberg terminal" | ⚠️ No external corroboration | 0–100 Deal Score (47 factors) + underwriting studio |
| **SiteScouter** (PermitPortal) | ❌ US, 1 preview city | AI site-sourcing | ⚠️ Thin, 2-person YC | NL site search + **ParcelMerge** (multi-parcel assembly) |
| **TerraScout** (→Ploti) | ❌ US-only | AI land search + deal pipeline | ✅ Live, $50–200/mo | NL query → map filters; deal CRM |
| **SiteIntel** | ❌ Texas-only | Feasibility-score PDF | ⚠️ Likely thin/vaporware | "Lender-ready" 60-sec feasibility PDF |
| **Civil Intelligence** | ❌ US/NY | Land-screening + climate risk | ⚠️ Thin marketing site | Climate/flood-aware feasibility score |
| **Qlocator** (Lumegis) | ❌ US-only | Geospatial site-selection | ⚠️ Brand-new, no traction | NL query over 500+ datasets |
| **Sitescope** | ❌ EU-only | Zoning-PDF → parcel intelligence | ⚠️ Waitlist-stage | Multilingual zoning extraction w/ source citations |
| **Permitify** | ❌ US-only | Site feasibility / plan review | ⚠️ Seed, ~3 ppl | Source-backed zoning Q&A; plan-review origins |

## What WE have that THEY don't (our edge — keep leaning on this)

1. **Council-vote / approval prediction** — ML on real Toronto voting records, swing-councillor flagging, "change X to shift the outcome." **Zero** competitors have anything political. This is the single most defensible thing we do.
2. **Community-opposition simulation** — deputation-volume forecast, opposition letters in the neighborhood's actual voice, named resident groups. **No analog anywhere** in the 14.
3. **Generated 3D massing/design options** fit to the legal envelope. Only Sitescope shows even a basic "buildable envelope visual"; nobody generates design schemes.
4. **Full DCF pro-forma (IRR 5/10yr + sensitivity).** Most competitors stop at a "feasibility score" or simple cost/rent. Even LandLogic's Multiplex stops at cost + projected rent — **no DCF/IRR**.
5. **End-to-end "replace the $150K consultant" brief** — others sell a data layer or a screening score; we synthesize the whole go/no-go decision.

> Strategic read: against the 12 US/EU tools, **Toronto depth + politics + community** all stack. Against **LandLogic and Zoneomics** (who own Toronto zoning), drop the "we have the data" framing — win explicitly on **politics, community, 3D design, and real DCF**, which neither has.

## What we could ADD from them — hackathon-ranked

Ranked by impact ÷ effort. Top tier is cheap and demo-defining.

### Tier 1 — do these (high impact, low effort, reuses data we already compute)

1. **Composite "go/no-go" Developability Score (0–100).** Roll our six sections into one headline number with explainable sub-weights. _Mentioned by AtlasIQ, SiteIntel, Civil Intelligence, SiteScouter — it's the expected UX hook. Pure presentation layer over data we already have._
2. **Source-cited zoning provenance.** Attach the exact By-law 569-2013 clause + open-data record ID/link to every Site Fundamentals number. _Sitescope, Permitify, Zoneomics all lead with "source-backed." We already do the point-in-polygon; just surface provenance. Big credibility win, near-free._
3. **Polished PDF / shareable brief export.** One-click branded, exportable, link-shareable brief. _Universal across LandVision, Land id, Zoneomics (certified letters), SiteIntel. Makes us feel "decision-grade." Mostly templating._
4. **Natural-language Q&A / chat over the brief.** "Can I get a setback exception?" / "What if affordable share is 20%?" scoped to the generated brief, on our local LLM. _TerraScout, SiteScouter, Qlocator, LandLogic, Zoneomics all have this now — it's table stakes. We already have a local model._
5. **Missing-middle / Multiplex viability flag.** "This lot qualifies as-of-right for a fourplex–sixplex." _LandLogic's GTA hero feature; we can derive it directly from the zoning envelope we already compute. Directly neutralizes our most threatening competitor._

### Tier 2 — strong if time allows (medium effort)

6. **Natural-language → parcel search + multi-parcel ranking.** Type criteria ("≥6 storeys, near transit, FSI headroom"), get ranked parcels. _The single most common competitor feature (SiteScouter, TerraScout, Qlocator, AtlasIQ, Zoneomics, LandLogic). Inverts our point-in-polygon into a filter query over the same dataset. Turns a one-shot tool into a workflow._
7. **"What should I pay?" — back-solve max land price for a target IRR.** One extra calc on our existing DCF. _AtlasIQ-style; very saleable to acquisition buyers._
8. **Comparable-sales panel.** Ground the pro-forma in recent nearby Toronto sales (TRREB/MPAC/open data). _AtlasIQ, LandVision, Land id. Strengthens the weakest-credibility part of our financial model._
9. **Flood / conservation environmental overlay.** Add TRCA flood + conservation layers to Site Constraints as map toggles. _SiteIntel, Civil Intelligence, Qlocator all foreground climate/flood. Partially overlaps what we already do._
10. **Past-application / Committee-of-Adjustment history near the parcel.** Surfaces prior variances — overlaps LightBox PZR's variance docs **and feeds our approval forecast.**

### Tier 3 — only if it's free (skip under time pressure)

11. **Multi-parcel assembly hints (ParcelMerge-style)** — flag adjacent compatible-zoning lots (SiteScouter). Pure adjacency + zoning logic, but niche for a demo.
12. **Building-footprint overlay** for massing realism (Regrid) — easy from Toronto open data.
13. **Owner / assessment / transaction panel** (LightBox, LandVision) — CRE table-stakes, data-sourcing dependent.
14. **Per-field freshness / confidence indicator** (Regrid coverage map, Permitify "no stale PDFs") — cheap trust-builder.
15. **Embeddable/branded public brief link** (Land id) — distribution play, low effort if export already exists.

## Recommended hackathon move

Spend the limited time on **Tier 1 items 1–5**. They're cheap, they demo well, and each directly answers a feature a judge will have seen in a competitor — while our **council-vote + community-opposition + 3D + DCF** stack remains something **none** of these 14 can show. Item 5 (Multiplex flag) specifically blunts LandLogic, the only real Toronto incumbent.
