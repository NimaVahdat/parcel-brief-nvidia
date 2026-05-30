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
  bylaw_reference?: string | null;
  missing_middle?: string | null;
};

export type SiteConstraints = {
  parcel_id: string;
  heritage_status: "none" | "listed" | "designated";
  tree_canopy_area_m2: number;
  sun_shadow_rules: string[];
  conservation_overlays: string[];
  transit_distance_m: number;
  easements: string[];
  fire_station_distance_m?: number | null;
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
  developability_score?: number;
  score_breakdown?: Record<string, number>;
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

export const CONNECTOR_BASE =
  process.env.NEXT_PUBLIC_CONNECTOR_URL ?? "http://localhost:8000";
const BASE_URL = CONNECTOR_BASE;

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

export type StreamHandlers = {
  onAgent: (node: string) => void;
  onBrief: (brief: BriefResponse, cached: boolean) => void;
  onError: (message: string) => void;
};

// Optional project overrides — when set, the brief evaluates *this* building.
export type ProjectOverrides = {
  height_m?: number;
  total_units?: number;
  affordable_units?: number;
  retail_sqft?: number;
};

// Streams real agent-completion events (SSE), then the final brief. Returns a
// cleanup fn. Cached parcels (same overrides) emit all steps + the brief instantly.
export function analyzeStream(
  parcelId: string,
  overrides: ProjectOverrides,
  handlers: StreamHandlers
): () => void {
  const params = new URLSearchParams({ parcel_id: parcelId });
  for (const [k, v] of Object.entries(overrides)) {
    if (v !== undefined && v !== null && !Number.isNaN(v)) params.set(k, String(v));
  }
  const es = new EventSource(`${BASE_URL}/analyze/stream?${params.toString()}`);
  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.brief) {
        handlers.onBrief(data.brief as BriefResponse, Boolean(data.cached));
        es.close();
      } else if (data.error) {
        handlers.onError(String(data.error));
        es.close();
      } else if (data.agent) {
        handlers.onAgent(String(data.agent));
      }
    } catch {
      /* ignore malformed keep-alive frames */
    }
  };
  es.onerror = () => {
    handlers.onError("Connection to the analysis server was lost.");
    es.close();
  };
  return () => es.close();
}
