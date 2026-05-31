// TypeScript types mirroring connector/src/connector/schemas/brief.py.
// If you change the Pydantic schema, update these too — they're the contract.

export type ZoningEnvelope = {
  parcel_id: string;
  max_height_m: number;
  max_fsi: number;
  setbacks: Record<string, number>;
  permitted_uses: string[];
  footprint_polygon: [number, number][];
  parking_minimum: number | null;
};

export type SiteConstraints = {
  parcel_id: string;
  heritage_status: "none" | "listed" | "designated";
  tree_canopy_area_m2: number;
  sun_shadow_rules: string[];
  conservation_overlays: string[];
  transit_distance_m: number;
  easements: string[];
};

export type Massing = {
  massing_id: string;
  height_m: number;
  total_gfa_m2: number;
  unit_mix: Record<string, number>;
  retail_sqft: number;
  affordable_units: number;
  three_d_uri: string;
  facade_renders: string[];
};

export type MassingOutput = { options: Massing[] };

export type FinancialModel = {
  construction_cost: number;
  projected_annual_rent: number;
  projected_sale_price: number | null;
  debt_service: number;
  irr_5y: number;
  irr_10y: number;
  sensitivities: Record<string, Record<string, number>>;
};

export type Lever = { change: string; delta_probability: number };

export type VotePrediction = {
  approval_probability: number;
  per_councillor: Record<string, number>;
  swing_councillors: string[];
  levers: Lever[];
};

export type Letter = {
  text: string;
  inferred_concerns: string[];
  source_neighborhood: string;
};

export type OppositionForecast = {
  expected_letter_count: number;
  sample_letters: Letter[];
  top_concerns: Record<string, number>;
  organized_groups: string[];
  mitigations: string[];
};

export type GoNoGo = {
  recommendation: "buy" | "pass" | "conditional";
  confidence: number;
  dominant_sensitivities: string[];
  rationale: string;
};

export type BriefResponse = {
  parcel_id: string;
  site_fundamentals: ZoningEnvelope;
  site_constraints: SiteConstraints;
  design_options: MassingOutput;
  financial_model: FinancialModel;
  approval_forecast: VotePrediction;
  community_response: OppositionForecast;
  recommendation: GoNoGo;
};

export const BASE_URL =
  process.env.NEXT_PUBLIC_CONNECTOR_URL ?? "http://localhost:8000";

export type MassingRender = { html_url: string };

// Renders one design option's spec to an interactive 3D HTML view and returns
// its URL (served by the connector under /renders). Slow — runs the pyvista
// render pipeline server-side.
export async function renderMassing(
  massingId: string,
  glb = true,
): Promise<MassingRender> {
  const res = await fetch(
    `${BASE_URL}/massing/${encodeURIComponent(massingId)}/render?glb=${glb}`,
    { method: "POST", cache: "no-store" },
  );
  if (!res.ok) {
    throw new Error(`Render failed ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

export async function analyze(parcelId: string): Promise<BriefResponse> {
  const res = await fetch(`${BASE_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parcel_id: parcelId }),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Connector returned ${res.status}: ${await res.text()}`);
  }
  return res.json();
}
