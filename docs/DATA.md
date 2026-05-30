# Verified Data Sources

All URLs below have been verified to resolve. Two project risks (per-councillor committee votes, deputation PDF quality) were also investigated against a real recent application — findings at the bottom.

Each component owns whichever subset of these it needs. There is no central ingest pipeline.

## City of Toronto Open Data

**Zoning By-law 569-2013 (spatial)**
https://open.toronto.ca/dataset/zoning-by-law/
Parcel-level zoning: zone codes, height overlay, lot coverage, setbacks, parking, policy overlays. 10 sub-layers, ~11,719 zoning-area polygons. Formats: Shapefile, GeoJSON, GeoPackage, CSV.
*Note: must be read with the by-law text; geometry alone is not legally definitive.*

**Property Boundaries (parcels)**
https://open.toronto.ca/dataset/property-boundaries/
~498k parcel polygons. Formats: Shapefile, GeoJSON, GeoPackage, CSV (WGS84 4326 and MTM 2952). Refresh: daily.

**Development Applications (AIC)**
https://open.toronto.ca/dataset/development-applications/
All open/closed Community Planning and Committee of Adjustment applications since 2008-01-01. ~26k records. Formats: CSV, XML, JSON. Refresh: daily.

**Building Permits — Active Permits**
https://open.toronto.ca/dataset/building-permits-active-permits/
~229k records. Formats: CSV, XML, JSON. Refresh: daily.

**Heritage Register**
https://open.toronto.ca/dataset/heritage-register/
Designated + listed properties under the Ontario Heritage Act. Complementary datasets exist for Heritage Conservation Districts, Heritage Formerly Listed, and OPA-720 CHER properties.
*Note: under Bill 23, listed (non-designated) properties expire from the register on 2027-01-01 unless designated — register churn is high through 2026.*

**Street Tree Data**
https://open.toronto.ca/dataset/street-tree-data/
~530k street-tree points (species, DBH, address).

**Tall Building Design Guidelines (sun/shadow rules)**
- https://www.toronto.ca/wp-content/uploads/2018/01/96ea-cityplanning-tall-buildings-may2013-final-AODA.pdf
- Downtown supplement: https://www.toronto.ca/wp-content/uploads/2018/03/9712-City-Planning-Downtown-Tall-Building-Web.pdf
- Sun/Shadow Terms of Reference checklist: https://www.toronto.ca/wp-content/uploads/2022/04/8e30-CityPlanning-Sun-Shadow-TORChecklist.pdf
Format: text-extractable PDF. Rule of thumb: 5h sunlight at equinoxes on opposite sidewalk.

**TTC Routes and Schedules (GTFS)**
https://open.toronto.ca/dataset/ttc-routes-and-schedules/
Format: GTFS zip (~35.6 MB). Refresh: ~monthly.

**311 Service Requests (Customer Initiated)**
https://open.toronto.ca/dataset/311-service-requests-customer-initiated/
Per-year ZIP/CSV, 2017–2026. Refresh: monthly.

## Toronto and Region Conservation Authority

**TRCA Regulated Areas / Regulation Limit**
- https://trca-camaps.opendata.arcgis.com/datasets/trca-regulated-area-opendata
- https://trca-camaps.opendata.arcgis.com/datasets/trca-regulation-limit-opendata/explore
- Catalog: https://data.trca.ca/dataset/gis-spatial-data
Floodplain / conservation overlays under O. Reg. 41/24.

## TMMIS (council meetings, votes, deputations)

**TMMIS public site**
- https://secure.toronto.ca/council/
- Legacy app: https://app.toronto.ca/tmmis/index.do?m=d

**Per-member vote report (CSV export)**
https://app.toronto.ca/tmmis/getAdminReport.do?function=prepareMemberVoteReport

**Voting & attendance landing page**
https://www.toronto.ca/legdocs/tmmis/votes-and-attendance.htm

Agenda items + static documents live under `https://www.toronto.ca/legdocs/mmis/YYYY/<body>/...`. **No official JSON API — scrape required. Akamai blocks server-side fetches (403). Use a headless browser (Playwright) or rotated UAs.**

**Community deputations / written submissions**
Attached on each TMMIS agenda item under `legdocs/mmis/YYYY/<committee>/comm/communicationfile-<id>.pdf`.

## Federal sources

**CMHC Rental Market Survey**
https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/rental-market/rental-market-report-data-tables
Vacancy, average rent, turnover by CMA and zone/neighbourhood. Toronto CMA has zone-level tables. Format: XLSX.

**Statistics Canada 2021 Census**
- https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/index-eng.cfm
- Census Profile by census tract: https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/index.cfm?Lang=E
- Bulk download: https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger.cfm
Census-tract-level demographics for Toronto CMA (CMA code 535).

## Risk investigation findings

**Does TMMIS expose individual councillor votes at the committee level?**
Yes. Voting & attendance covers Council and committee meetings since 1999, and the Voting Record report tool generates per-member records as CSV. *Caveat:* a vote is only recorded when a recorded vote is called — many routine committee motions pass on voice vote. For contentious development items, recorded votes are routinely requested, so coverage is good but not 100%.

**Are deputations text-extractable PDFs or scans?**
Text-extractable in the cases sampled. A real deputation letter (`legdocs/mmis/2023/ec/comm/communicationfile-170032.pdf`) returned clean structured text via `pdftotext`. *Caveat:* expect ~10–20% (older items, handwritten letters, marked-up plans) to be image-only and require OCR fallback.

Both risks are green. The vote-prediction and opposition-retrieval corpora exist.

## Component → Dataset Mapping

| Component | Datasets |
|---|---|
| `vote-predictor` | TMMIS (applications + recorded votes) |
| `opposition-generator` | TMMIS (deputation PDFs) |
| `massing-generator` | Toronto building photos (collected separately) |
| `site-proforma` | Zoning, parcels, heritage, trees, transit, sun-shadow, TRCA, CMHC, StatsCan |
| `connector` | None (orchestration only) |
| `ui` | None |
