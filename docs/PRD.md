# PRD: Toronto Site Pre-Acquisition Analysis System

## 1. Overview

A web tool that produces a pre-acquisition analysis for any Toronto parcel in a few minutes. Given a parcel ID or address, it returns a Development Brief: legal building envelope, site constraints, candidate designs, financial projections, predicted approval outcome at council, and predicted community response.

Users are real estate developers, brokers, and municipal planners doing early-stage site screening.

## 2. Problem

A pre-acquisition brief today is assembled by a team of consultants: a planner, an architect, a quantity surveyor, a real estate analyst, a government-relations advisor, and a community-engagement firm. It takes four to eight weeks and costs $150K to $300K.

That cost forces developers to commission full briefs only on sites they're already inclined to buy. A developer with a 50-site quarterly pipeline typically gets full analysis on one to three. The rest of the market gets screened informally or skipped.

## 3. Rationale

Two things changed in the last two years that make this feasible now.

Toronto's relevant records (zoning as a parcel-keyed spatial layer, planning applications, committee agendas, recorded vote outcomes, community deputation submissions) are now machine-accessible. They weren't before.

Open-weight models in the 7–14B range are good enough for the domain reasoning the workflow needs, paired with the right adaptation. Two of the six analysis sections need capability that no frontier API ships with: predicting how Toronto council will vote on a specific project, and writing in the voice of a specific Toronto neighborhood. The first is a statistical prediction problem best solved by training on Toronto's voting record. The second is a generation problem best solved by retrieving real past deputations as in-context examples. Both run comfortably on the GB10.

Without open data the system has no inputs. Without local adaptation it's another LLM wrapper.

## 4. User Experience

The user opens a map of Toronto, picks a parcel by address search or click, and hits Analyze.

A few minutes later they get a Development Brief in six sections.

**Site Fundamentals.** The legal building envelope under current zoning: maximum height, FSI, setbacks, permitted uses, parking minimums.

**Site Constraints.** Heritage status, tree canopy, sun-shadow rules affecting adjacent parks or sidewalks, conservation authority overlays, transit access, easements.

**Design Options.** Two or three building massings rendered in 3D, each fitting the envelope and respecting site constraints.

**Financial Model.** Construction cost, projected rents or sale prices using public comparables, debt service, IRR over 5 and 10 years, sensitivity to rates and stabilization timeline.

**Approval Forecast.** Predicted vote at the relevant community council and at full council. Where individual votes are available, the swing councillors are flagged. Recommended project changes that would shift the outcome (affordable units, ground-floor retail, community space).

**Community Response Forecast.** Expected volume of deputations, sample letters in the voice of the actual neighborhood, names of the resident groups likely to organize, and changes historically associated with reduced opposition.

A closing synthesis gives a go/no-go with confidence and the dominant sensitivities. The brief exports to PDF.

The user can adjust project parameters (unit count, affordable share, retail allocation) and re-run. Re-runs reuse cached site data and complete in under 20 seconds.

## 5. System Design

The system is built as six independent components communicating through five fixed contracts. See `docs/CONTRACTS.md` for the interface definitions.

- **vote-predictor** — tabular classifier (XGBoost) over structured application features, with a Qwen2.5-7B wrapper that parses unstructured application text on input and writes natural-language counterfactuals on output. Trained on TMMIS application + vote records. The split is deliberate: vote prediction is a statistical problem, and a tabular model on the right features beats fine-tuning a 7B for both accuracy and inference cost; the LLM earns its keep at the I/O boundary.
- **opposition-generator** — retrieval over the deputation corpus (text extracted from TMMIS PDFs, embedded with sentence-transformers, indexed in pgvector) feeding a strong instruction-tuned open model (Qwen2.5-14B). No fine-tuning; the retrieved letters carry the neighborhood voice.
- **massing-generator** — SDXL with ControlNet conditioned on the legal envelope geometry. Optional light LoRA on Toronto building photos for stylistic fidelity.
- **site-proforma** — Toronto Open Data ingestion (zoning, parcels, heritage, trees, transit, sun-shadow) normalized to parcel-keyed tables; deterministic financial math against CMHC neighborhood rents.
- **connector** — LangGraph orchestrator that calls the four components in parallel where possible and synthesizes the six-section brief; FastAPI service.
- **ui** — Next.js front end: Toronto map with parcel selection and a brief viewer.

Training the Vote Predictor and inference for all models run on the GB10. No external APIs are called at inference time, which the unit economics require.
