import type { BriefResponse } from "@/lib/api";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      <div className="text-sm text-neutral-800">{children}</div>
    </section>
  );
}

export default function BriefViewer({ brief }: { brief: BriefResponse }) {
  const env = brief.site_fundamentals;
  const con = brief.site_constraints;
  const fin = brief.financial_model;
  const approval = brief.approval_forecast;
  const opp = brief.community_response;
  const rec = brief.recommendation;
  const massing = brief.design_options.options[0];

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Section title={`Recommendation — ${rec.recommendation.toUpperCase()}`}>
        <p className="mb-2">{rec.rationale}</p>
        <p className="text-neutral-600">
          Confidence: {(rec.confidence * 100).toFixed(0)}%
        </p>
      </Section>

      <Section title="Site Fundamentals">
        <ul className="list-disc pl-5">
          <li>Max height: {env.max_height_m} m</li>
          <li>Max FSI: {env.max_fsi}</li>
          <li>Permitted uses: {env.permitted_uses.join(", ")}</li>
          <li>Parking minimum: {env.parking_minimum ?? "n/a"}</li>
        </ul>
      </Section>

      <Section title="Site Constraints">
        <ul className="list-disc pl-5">
          <li>Heritage: {con.heritage_status}</li>
          <li>Transit distance: {con.transit_distance_m} m</li>
          <li>Tree canopy: {con.tree_canopy_area_m2} m²</li>
          {con.sun_shadow_rules.map((r) => (
            <li key={r}>Sun-shadow: {r}</li>
          ))}
        </ul>
      </Section>

      <Section title="Design (first option)">
        <ul className="list-disc pl-5">
          <li>Height: {massing.height_m} m</li>
          <li>GFA: {massing.total_gfa_m2.toLocaleString()} m²</li>
          <li>Affordable units: {massing.affordable_units}</li>
          <li>Retail: {massing.retail_sqft} sqft</li>
        </ul>
      </Section>

      <Section title="Financial Model">
        <ul className="list-disc pl-5">
          <li>Construction cost: ${fin.construction_cost.toLocaleString()}</li>
          <li>Annual rent: ${fin.projected_annual_rent.toLocaleString()}</li>
          <li>IRR (5y): {(fin.irr_5y * 100).toFixed(1)}%</li>
          <li>IRR (10y): {(fin.irr_10y * 100).toFixed(1)}%</li>
        </ul>
      </Section>

      <Section title="Approval Forecast">
        <p>
          Predicted approval probability:{" "}
          <strong>{(approval.approval_probability * 100).toFixed(0)}%</strong>
        </p>
        <p className="mt-2 text-neutral-600">
          Swing: {approval.swing_councillors.join(", ") || "none"}
        </p>
        <p className="mt-2 font-medium">Levers</p>
        <ul className="list-disc pl-5">
          {approval.levers.map((l) => (
            <li key={l.change}>
              {l.change} (Δ +{(l.delta_probability * 100).toFixed(0)}%)
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Community Response">
        <p>
          Expected letters: <strong>~{opp.expected_letter_count}</strong>
        </p>
        <p className="mt-2 text-neutral-600">
          Groups: {opp.organized_groups.join(", ")}
        </p>
        <p className="mt-2 font-medium">Top concerns</p>
        <ul className="list-disc pl-5">
          {Object.entries(opp.top_concerns).map(([k, v]) => (
            <li key={k}>
              {k} — {(v * 100).toFixed(0)}%
            </li>
          ))}
        </ul>
        {opp.sample_letters[0] && (
          <>
            <p className="mt-3 font-medium">Sample letter</p>
            <p className="mt-1 whitespace-pre-wrap rounded bg-neutral-50 p-3 italic text-neutral-700">
              {opp.sample_letters[0].text}
            </p>
          </>
        )}
      </Section>
    </div>
  );
}
