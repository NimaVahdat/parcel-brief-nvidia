import { describe, it, expect } from "vitest";
import type { BriefResponse } from "@/lib/api";
import { buildReportModel } from "./buildReportModel";
import { SECTION_ORDER } from "./sections";
import type { ReportSection } from "./types";

// ── fixture ──────────────────────────────────────────────────────────────────

function makeBrief(): BriefResponse {
  return {
    parcel_id: "1145-DANFORTH-AVE",
    site_fundamentals: {
      parcel_id: "1145-DANFORTH-AVE",
      max_height_m: 26,
      max_fsi: 3.5,
      setbacks: { front: 3, rear: 7.5 },
      permitted_uses: ["residential", "retail"],
      footprint_polygon: [[0, 0]],
      parking_minimum: null,
      bylaw_reference: "Zoning By-law 569-2013",
      missing_middle: "Eligible for fourplex as-of-right",
    },
    site_constraints: {
      parcel_id: "1145-DANFORTH-AVE",
      heritage_status: "listed",
      tree_canopy_area_m2: 120,
      sun_shadow_rules: ["5pm equinox protection"],
      conservation_overlays: [],
      transit_distance_m: 180,
      easements: ["Hydro easement (rear)"],
      fire_station_distance_m: 640,
    },
    design_options: {
      options: [
        {
          massing_id: "opt-a",
          height_m: 24,
          total_gfa_m2: 4200,
          unit_mix: { studio: 8, "1br": 20, "2br": 12 },
          retail_sqft: 1500,
          affordable_units: 8,
          three_d_uri: "/massing/opt-a",
          facade_renders: [],
        },
        {
          massing_id: "opt-b",
          height_m: 26,
          total_gfa_m2: 4800,
          unit_mix: { "1br": 28, "2br": 14 },
          retail_sqft: 0,
          affordable_units: 10,
          three_d_uri: "/massing/opt-b",
          facade_renders: [],
        },
      ],
    },
    financial_model: {
      construction_cost: 18_500_000,
      projected_annual_rent: 2_400_000,
      projected_sale_price: 34_000_000,
      debt_service: 1_100_000,
      irr_5y: 0.142,
      irr_10y: 0.181,
      sensitivities: {
        "rent -10%": { irr_5y: 0.101, sale_price: 30_000_000 },
        "cost +10%": { irr_5y: 0.118, sale_price: 33_000_000 },
      },
    },
    approval_forecast: {
      approval_probability: 0.64,
      per_councillor: { "Ward 14": 0.7, "Ward 19": 0.4 },
      swing_councillors: ["Ward 19"],
      levers: [{ change: "Add 4 affordable units", delta_probability: 0.08 }],
    },
    community_response: {
      expected_letter_count: 35,
      sample_letters: [
        {
          text: "We are concerned about shadowing on the adjacent park.",
          inferred_concerns: ["shadow"],
          source_neighborhood: "Playter Estates",
        },
      ],
      top_concerns: { shadow: 0.4, traffic: 0.3, density: 0.3 },
      organized_groups: ["Playter Estates Residents Assoc."],
      mitigations: ["Step back upper storeys"],
    },
    recommendation: {
      recommendation: "buy",
      confidence: 0.78,
      developability_score: 72,
      score_breakdown: { zoning: 30, financial: 25, approval: 17 },
      dominant_sensitivities: ["rent", "approval"],
      rationale: "Strong transit access and as-of-right density support acquisition.",
    },
  };
}

// ── helpers ──────────────────────────────────────────────────────────────────

function ids(model: ReportSection[]): string[] {
  return model.map((s) => s.id);
}

function sectionText(section: ReportSection): string {
  return JSON.stringify(section.blocks);
}

// ── tests ────────────────────────────────────────────────────────────────────

describe("buildReportModel", () => {
  it("returns all six sections in canonical order when everything is selected", () => {
    const model = buildReportModel(makeBrief(), new Set(SECTION_ORDER));
    expect(ids(model)).toEqual([...SECTION_ORDER]);
  });

  it("returns only the selected sections, still in canonical order", () => {
    // intentionally out of order in the input set
    const model = buildReportModel(
      makeBrief(),
      new Set(["financial-model", "executive-summary"])
    );
    expect(ids(model)).toEqual(["executive-summary", "financial-model"]);
  });

  it("returns an empty model when nothing is selected", () => {
    const model = buildReportModel(makeBrief(), new Set());
    expect(model).toEqual([]);
  });

  it("accepts an array of ids as well as a Set", () => {
    const model = buildReportModel(makeBrief(), ["site"]);
    expect(ids(model)).toEqual(["site"]);
  });

  it("executive summary carries the recommendation, score and confidence", () => {
    const [exec] = buildReportModel(makeBrief(), ["executive-summary"]);
    const text = sectionText(exec);
    expect(exec.heading).toMatch(/executive summary/i);
    expect(text.toLowerCase()).toContain("buy");
    expect(text).toContain("72"); // developability score
    expect(text).toContain("78"); // confidence %
    expect(text).toContain("Strong transit access"); // rationale
  });

  it("financial model carries IRR and cost figures", () => {
    const [fin] = buildReportModel(makeBrief(), ["financial-model"]);
    const text = sectionText(fin);
    expect(text).toContain("14.2%"); // IRR 5y
    expect(text).toContain("18.1%"); // IRR 10y
    expect(text).toMatch(/\$18\.5M/); // construction cost
  });

  it("design options includes every option, not just the first", () => {
    const [design] = buildReportModel(makeBrief(), ["design-options"]);
    const text = sectionText(design);
    expect(text).toContain("opt-a");
    expect(text).toContain("opt-b");
  });

  it("approval & community section merges both forecasts", () => {
    const [sec] = buildReportModel(makeBrief(), ["approval-community"]);
    const text = sectionText(sec).toLowerCase();
    expect(text).toContain("ward 19"); // swing councillor
    expect(text).toContain("shadow"); // top concern
  });
});
