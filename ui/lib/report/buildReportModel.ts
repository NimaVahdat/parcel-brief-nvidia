import type {
  BriefResponse,
  FinancialModel,
  Massing,
  OppositionForecast,
  SiteConstraints,
  VotePrediction,
  ZoningEnvelope,
} from "@/lib/api";
import type { ReportBlock, ReportModel, ReportSection, SectionId } from "./types";
import { orderedSelection } from "./selection";
import { fmtMoney, fmtPct, fmtSensitivity, oppositionLabel } from "./format";

/**
 * Capitalises the first character of a label (e.g. "shadow" → "Shadow").
 *
 * @param {string} s - The string to capitalise.
 * @returns {string} The input with its first character upper-cased.
 */
function capitalize(s: string): string {
  return s.length === 0 ? s : s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * Sums all unit counts in a massing option's unit mix.
 *
 * @param {Massing} option - The massing option to total.
 * @returns {number} The total number of residential units.
 */
function totalUnits(option: Massing): number {
  return Object.values(option.unit_mix).reduce((sum, n) => sum + n, 0);
}

/**
 * Produces the plain-language approval narrative shown on the brief, derived
 * from the council approval probability.
 *
 * @param {number} probability - The 0–1 approval probability.
 * @returns {string} A sentence describing the likelihood of approval.
 */
function approvalNarrative(probability: number): string {
  const pct = Math.round(probability * 100);
  if (pct >= 70)
    return `At ${pct}%, council approval is likely. The project has a strong majority position.`;
  if (pct >= 50)
    return `At ${pct}%, the vote is uncertain. A handful of councillors will determine the outcome.`;
  return `At ${pct}%, approval is unlikely without material changes to the application.`;
}

// ── section builders ──────────────────────────────────────────────────────────

/**
 * Builds the Executive Summary section from the go/no-go recommendation.
 *
 * @param {BriefResponse} brief - The full brief.
 * @returns {ReportSection} The assembled executive summary section.
 */
function buildExecutiveSummary(brief: BriefResponse): ReportSection {
  const rec = brief.recommendation;
  const rows: Array<{ label: string; value: string }> = [
    { label: "Recommendation", value: rec.recommendation.toUpperCase() },
  ];
  if (rec.developability_score != null) {
    rows.push({ label: "Developability score", value: `${rec.developability_score}/100` });
  }
  rows.push({ label: "Confidence", value: fmtPct(rec.confidence) });
  rows.push({
    label: "Approval probability",
    value: fmtPct(brief.approval_forecast.approval_probability),
  });

  const blocks: ReportBlock[] = [{ kind: "keyValue", rows }];
  blocks.push({ kind: "paragraph", text: rec.rationale });
  if (rec.dominant_sensitivities.length > 0) {
    blocks.push({ kind: "bullets", label: "Key risks", items: rec.dominant_sensitivities });
  }
  if (rec.score_breakdown && Object.keys(rec.score_breakdown).length > 0) {
    blocks.push({
      kind: "keyValue",
      rows: Object.entries(rec.score_breakdown).map(([k, v]) => ({
        label: capitalize(k),
        value: String(v),
      })),
    });
  }
  return { id: "executive-summary", heading: "Executive Summary", blocks };
}

/**
 * Builds the Key Metrics section — the four headline figures.
 *
 * @param {BriefResponse} brief - The full brief.
 * @returns {ReportSection} The assembled key metrics section.
 */
function buildKeyMetrics(brief: BriefResponse): ReportSection {
  const env = brief.site_fundamentals;
  const fin = brief.financial_model;
  return {
    id: "key-metrics",
    heading: "Key Metrics",
    blocks: [
      {
        kind: "keyValue",
        rows: [
          { label: "Approval probability", value: fmtPct(brief.approval_forecast.approval_probability) },
          { label: "IRR (5-year)", value: fmtPct(fin.irr_5y, 1) },
          { label: "Max height", value: `${env.max_height_m} m` },
          { label: "Max FSI", value: String(env.max_fsi) },
          { label: "Construction cost", value: fmtMoney(fin.construction_cost) },
        ],
      },
    ],
  };
}

/**
 * Builds the approval-forecast blocks (probability, narrative, swing
 * councillors, levers).
 *
 * @param {VotePrediction} approval - The council vote prediction.
 * @returns {ReportBlock[]} The approval-forecast content blocks.
 */
function buildApprovalBlocks(approval: VotePrediction): ReportBlock[] {
  const blocks: ReportBlock[] = [
    { kind: "subheading", text: "Approval Forecast" },
    {
      kind: "keyValue",
      rows: [{ label: "Approval probability", value: fmtPct(approval.approval_probability) }],
    },
    { kind: "paragraph", text: approvalNarrative(approval.approval_probability) },
  ];
  if (approval.swing_councillors.length > 0) {
    blocks.push({ kind: "bullets", label: "Swing councillors", items: approval.swing_councillors });
  }
  if (approval.levers.length > 0) {
    blocks.push({
      kind: "bullets",
      label: "Levers to improve approval",
      items: approval.levers.map((l) => `${l.change} (+${fmtPct(l.delta_probability)})`),
    });
  }
  return blocks;
}

/**
 * Builds the community-response blocks (volume, groups, concerns, mitigations,
 * sample letter).
 *
 * @param {OppositionForecast} opp - The community opposition forecast.
 * @returns {ReportBlock[]} The community-response content blocks.
 */
function buildCommunityBlocks(opp: OppositionForecast): ReportBlock[] {
  const blocks: ReportBlock[] = [
    { kind: "subheading", text: "Community Response" },
    {
      kind: "keyValue",
      rows: [
        { label: "Expected deputations", value: `~${opp.expected_letter_count}` },
        { label: "Opposition level", value: oppositionLabel(opp.expected_letter_count) },
      ],
    },
  ];
  if (opp.organized_groups.length > 0) {
    blocks.push({ kind: "bullets", label: "Groups likely to organise", items: opp.organized_groups });
  }
  const concerns = Object.entries(opp.top_concerns).sort(([, a], [, b]) => b - a);
  if (concerns.length > 0) {
    blocks.push({
      kind: "bullets",
      label: "Top concerns",
      items: concerns.map(([concern, weight]) => `${capitalize(concern)} — ${fmtPct(weight)}`),
    });
  }
  if (opp.mitigations.length > 0) {
    blocks.push({ kind: "bullets", label: "Mitigations", items: opp.mitigations });
  }
  const letter = opp.sample_letters[0];
  if (letter) {
    blocks.push({
      kind: "paragraph",
      text: `Sample deputation — "${letter.text}" (${letter.source_neighborhood})`,
    });
  }
  return blocks;
}

/**
 * Builds the combined Approval Forecast & Community Response section.
 *
 * @param {BriefResponse} brief - The full brief.
 * @returns {ReportSection} The assembled section.
 */
function buildApprovalCommunity(brief: BriefResponse): ReportSection {
  return {
    id: "approval-community",
    heading: "Approval Forecast & Community Response",
    blocks: [
      ...buildApprovalBlocks(brief.approval_forecast),
      ...buildCommunityBlocks(brief.community_response),
    ],
  };
}

/**
 * Builds the Financial Model section — headline figures plus the sensitivity
 * table when present.
 *
 * @param {BriefResponse} brief - The full brief.
 * @returns {ReportSection} The assembled financial section.
 */
function buildFinancialModel(brief: BriefResponse): ReportSection {
  const fin: FinancialModel = brief.financial_model;
  const blocks: ReportBlock[] = [
    {
      kind: "keyValue",
      rows: [
        { label: "Construction cost", value: fmtMoney(fin.construction_cost) },
        { label: "Annual rent", value: fmtMoney(fin.projected_annual_rent) },
        {
          label: "Sale price",
          value: fin.projected_sale_price != null ? fmtMoney(fin.projected_sale_price) : "—",
        },
        { label: "Debt service", value: fmtMoney(fin.debt_service) },
        { label: "IRR (5-year)", value: fmtPct(fin.irr_5y, 1) },
        { label: "IRR (10-year)", value: fmtPct(fin.irr_10y, 1) },
      ],
    },
  ];

  const scenarios = Object.entries(fin.sensitivities);
  if (scenarios.length > 0) {
    const metricKeys = Object.keys(scenarios[0][1]);
    blocks.push({
      kind: "table",
      columns: ["Scenario", ...metricKeys],
      rows: scenarios.map(([scenario, metrics]) => [
        scenario,
        // Guard against a scenario whose key set differs from the first row's:
        // a missing metric renders as "—" rather than "$NaN".
        ...metricKeys.map((k) => (k in metrics ? fmtSensitivity(metrics[k]) : "—")),
      ]),
    });
  }
  return { id: "financial-model", heading: "Financial Model", blocks };
}

/**
 * Builds the Site Fundamentals & Constraints section from the zoning envelope
 * and site constraints.
 *
 * @param {BriefResponse} brief - The full brief.
 * @returns {ReportSection} The assembled site section.
 */
function buildSite(brief: BriefResponse): ReportSection {
  const env: ZoningEnvelope = brief.site_fundamentals;
  const con: SiteConstraints = brief.site_constraints;

  const fundamentals: Array<{ label: string; value: string }> = [
    { label: "Max height", value: `${env.max_height_m} m` },
    { label: "Max FSI", value: String(env.max_fsi) },
    {
      label: "Setbacks",
      value:
        Object.entries(env.setbacks)
          .map(([dir, m]) => `${dir} ${m} m`)
          .join(" · ") || "—",
    },
    { label: "Permitted uses", value: env.permitted_uses.join(", ") || "—" },
    {
      label: "Parking minimum",
      value: env.parking_minimum != null ? `${env.parking_minimum} spaces` : "No minimum",
    },
  ];
  if (env.bylaw_reference) fundamentals.push({ label: "Zoning source", value: env.bylaw_reference });

  const blocks: ReportBlock[] = [
    { kind: "subheading", text: "Site Fundamentals" },
    { kind: "keyValue", rows: fundamentals },
  ];
  if (env.missing_middle) {
    blocks.push({ kind: "paragraph", text: `Missing-middle eligibility: ${env.missing_middle}` });
  }

  const constraints: Array<{ label: string; value: string }> = [
    { label: "Heritage status", value: con.heritage_status },
    { label: "Transit distance", value: `${con.transit_distance_m} m` },
  ];
  if (con.fire_station_distance_m != null) {
    constraints.push({ label: "Nearest fire station", value: `${con.fire_station_distance_m} m` });
  }
  constraints.push({ label: "Tree canopy", value: `${con.tree_canopy_area_m2} m²` });

  blocks.push({ kind: "subheading", text: "Site Constraints" });
  blocks.push({ kind: "keyValue", rows: constraints });
  if (con.sun_shadow_rules.length > 0) {
    blocks.push({ kind: "bullets", label: "Sun-shadow rules", items: con.sun_shadow_rules });
  }
  if (con.conservation_overlays.length > 0) {
    blocks.push({ kind: "bullets", label: "Conservation overlays", items: con.conservation_overlays });
  }
  if (con.easements.length > 0) {
    blocks.push({ kind: "bullets", label: "Easements", items: con.easements });
  }
  return { id: "site", heading: "Site Fundamentals & Constraints", blocks };
}

/**
 * Builds the Design Options section, including every massing option (not just
 * the one selected on screen) so the report is self-contained.
 *
 * @param {BriefResponse} brief - The full brief.
 * @returns {ReportSection} The assembled design options section.
 */
function buildDesignOptions(brief: BriefResponse): ReportSection {
  const blocks: ReportBlock[] = [];
  brief.design_options.options.forEach((option, idx) => {
    const units = totalUnits(option);
    blocks.push({ kind: "subheading", text: `Option ${idx + 1} — ${option.massing_id}` });
    blocks.push({
      kind: "keyValue",
      rows: [
        { label: "Height", value: `${option.height_m} m` },
        { label: "Gross floor area", value: `${option.total_gfa_m2.toLocaleString()} m²` },
        { label: "Residential units", value: units > 0 ? String(units) : "—" },
        { label: "Affordable units", value: String(option.affordable_units) },
        {
          label: "Retail",
          value: option.retail_sqft > 0 ? `${option.retail_sqft.toLocaleString()} sqft` : "None",
        },
      ],
    });
    if (Object.keys(option.unit_mix).length > 0) {
      blocks.push({
        kind: "bullets",
        label: "Unit mix",
        items: Object.entries(option.unit_mix).map(([type, count]) => `${count}× ${type}`),
      });
    }
  });
  return { id: "design-options", heading: "Design Options", blocks };
}

// Dispatch table mapping each section id to its builder.
const BUILDERS: Record<SectionId, (brief: BriefResponse) => ReportSection> = {
  "executive-summary": buildExecutiveSummary,
  "key-metrics": buildKeyMetrics,
  "approval-community": buildApprovalCommunity,
  "financial-model": buildFinancialModel,
  site: buildSite,
  "design-options": buildDesignOptions,
};

/**
 * Assembles the ordered report model from a brief and a section selection.
 * Unselected sections are omitted; selected sections are emitted in canonical
 * document order regardless of selection order. This function is pure.
 *
 * @param {BriefResponse} brief - The brief currently shown (overrides already applied).
 * @param {Iterable<SectionId>} selected - The chosen section ids (Set or array).
 * @returns {ReportModel} The ordered list of assembled report sections.
 */
export function buildReportModel(
  brief: BriefResponse,
  selected: Iterable<SectionId>
): ReportModel {
  const selectedSet = selected instanceof Set ? selected : new Set(selected);
  return orderedSelection(selectedSet).map((id) => BUILDERS[id](brief));
}
