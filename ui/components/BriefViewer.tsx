"use client";

import { useState, useEffect, useRef } from "react";
import type { BriefResponse, Massing } from "@/lib/api";
import { BASE_URL, renderMassing } from "@/lib/api";

// ─── formatting helpers ───────────────────────────────────────────────────────

function fmtMoney(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function fmtPct(n: number, decimals = 0): string {
  return `${(n * 100).toFixed(decimals)}%`;
}

function irrColorClass(irr: number): string {
  if (irr >= 0.15) return "text-emerald-600";
  if (irr >= 0.08) return "text-amber-600";
  return "text-red-600";
}

function approvalColorClass(prob: number): string {
  if (prob >= 0.7) return "text-emerald-600";
  if (prob >= 0.5) return "text-amber-600";
  return "text-red-600";
}

function communityRisk(count: number): {
  label: string;
  color: string;
  bg: string;
  explanation: string;
} {
  if (count < 20)
    return {
      label: "Low",
      color: "text-emerald-700",
      bg: "bg-emerald-100",
      explanation:
        "Low expected opposition. Minimal community mobilisation likely.",
    };
  if (count < 60)
    return {
      label: "Moderate",
      color: "text-amber-700",
      bg: "bg-amber-100",
      explanation:
        "Some organised opposition expected. Targeted engagement recommended.",
    };
  return {
    label: "High",
    color: "text-red-700",
    bg: "bg-red-100",
    explanation:
      "Significant community opposition anticipated. Proactive outreach is critical.",
  };
}

// ─── animation hooks ──────────────────────────────────────────────────────────

function useCountUp(target: number, durationMs = 1100): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    let start: number | null = null;

    function step(ts: number) {
      if (!start) start = ts;
      const elapsed = ts - start;
      const p = Math.min(elapsed / durationMs, 1);
      const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
      setValue(eased * target);
      if (p < 1) rafRef.current = requestAnimationFrame(step);
    }

    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, durationMs]);

  return value;
}

// Returns true after a short delay, triggering CSS transitions on mount
function useDelayedReady(delayMs = 120): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setReady(true), delayMs);
    return () => clearTimeout(t);
  }, [delayMs]);
  return ready;
}

// ─── shared primitives ────────────────────────────────────────────────────────

function Card({
  title,
  children,
  className = "",
  style,
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`rounded-xl border border-slate-200 bg-white shadow-sm transition-shadow duration-200 hover:shadow-md ${className}`}
      style={style}
    >
      {title && (
        <div className="border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}

function AnimatedProbabilityBar({
  probability,
  label,
}: {
  probability: number;
  label: string;
}) {
  const pct = Math.round(probability * 100);
  const ready = useDelayedReady(200);
  const barColor =
    pct >= 70 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-400" : "bg-red-500";
  const textColor =
    pct >= 70
      ? "text-emerald-700"
      : pct >= 50
        ? "text-amber-700"
        : "text-red-700";

  return (
    <div>
      <div className="mb-1.5 flex justify-between text-xs">
        <span className={`font-semibold ${textColor}`}>{pct}%</span>
        <span className="text-slate-400">{label}</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-2.5 rounded-full ${barColor}`}
          style={{
            width: ready ? `${pct}%` : "0%",
            transition: "width 1.3s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
      </div>
    </div>
  );
}

function AnimatedConcernBar({
  concern,
  weight,
}: {
  concern: string;
  weight: number;
}) {
  const ready = useDelayedReady(300);
  return (
    <li>
      <div className="mb-1 flex justify-between text-xs">
        <span className="font-medium capitalize text-slate-700">{concern}</span>
        <span className="text-slate-400">{(weight * 100).toFixed(0)}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-1.5 rounded-full bg-red-400"
          style={{
            width: ready ? `${weight * 100}%` : "0%",
            transition: "width 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
      </div>
    </li>
  );
}

// ─── design option comparison ─────────────────────────────────────────────────

function DesignComparison({
  options,
  selectedIdx,
}: {
  options: Massing[];
  selectedIdx: number;
}) {
  if (options.length === 0) return null;

  const totalUnits = (opt: Massing) =>
    Object.values(opt.unit_mix).reduce((sum, n) => sum + n, 0);

  const rows: {
    label: string;
    getValue: (opt: Massing) => string;
    getNum: (opt: Massing) => number;
  }[] = [
    {
      label: "Height",
      getValue: (o) => `${o.height_m} m`,
      getNum: (o) => o.height_m,
    },
    {
      label: "Gross floor area",
      getValue: (o) => `${o.total_gfa_m2.toLocaleString()} m²`,
      getNum: (o) => o.total_gfa_m2,
    },
    {
      label: "Residential units",
      getValue: (o) => {
        const t = totalUnits(o);
        return t > 0 ? String(t) : "—";
      },
      getNum: totalUnits,
    },
    {
      label: "Affordable units",
      getValue: (o) => String(o.affordable_units),
      getNum: (o) => o.affordable_units,
    },
    {
      label: "Retail",
      getValue: (o) =>
        o.retail_sqft > 0 ? `${o.retail_sqft.toLocaleString()} sqft` : "None",
      getNum: (o) => o.retail_sqft,
    },
  ];

  const selected = options[selectedIdx];

  // Single option — show a tidy summary panel instead of a comparison table
  if (options.length === 1) {
    return (
      <div className="mt-5 animate-fade-in-up border-t border-slate-100 pt-5">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Design summary
        </p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {rows.map(({ label, getValue }) => (
            <div key={label} className="rounded-lg bg-slate-50 px-3 py-2.5">
              <p className="text-xs text-slate-500">{label}</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-800">
                {getValue(selected)}
              </p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Multiple options — side-by-side comparison table with directional deltas
  const selectedNums = rows.map((r) => r.getNum(options[selectedIdx]));

  return (
    <div className="mt-5 animate-fade-in-up border-t border-slate-100 pt-5">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
        Option {selectedIdx + 1} compared to alternatives
      </p>
      <div className="overflow-x-auto rounded-lg border border-slate-100">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr className="border-b border-slate-100">
              <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">
                Metric
              </th>
              {options.map((_, idx) => (
                <th
                  key={idx}
                  className="px-3 py-2 text-right text-xs font-semibold"
                >
                  {idx === selectedIdx ? (
                    <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5 text-blue-700">
                      Option {idx + 1}
                    </span>
                  ) : (
                    <span className="text-slate-400">Option {idx + 1}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50 bg-white">
            {rows.map(({ label, getValue, getNum }, rowIdx) => (
              <tr key={label}>
                <td className="px-3 py-2.5 text-xs text-slate-500">{label}</td>
                {options.map((opt, idx) => {
                  const isSelected = idx === selectedIdx;
                  const delta = isSelected
                    ? null
                    : getNum(opt) - selectedNums[rowIdx];
                  const hasDelta = delta !== null && delta !== 0;
                  return (
                    <td
                      key={idx}
                      className={`px-3 py-2.5 text-right text-xs ${
                        isSelected
                          ? "font-bold text-blue-800"
                          : "text-slate-400"
                      }`}
                    >
                      {getValue(opt)}
                      {hasDelta && (
                        <span
                          className={`ml-1 text-[10px] font-semibold ${
                            delta > 0 ? "text-emerald-500" : "text-red-400"
                          }`}
                          title={`${delta > 0 ? "+" : ""}${delta.toFixed(1)} vs selected`}
                        >
                          {delta > 0 ? "↑" : "↓"}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── selected option summary ─────────────────────────────────────────────────

function SelectedOptionSummary({
  option,
  idx,
}: {
  option: Massing;
  idx: number;
}) {
  const totalResidential = Object.values(option.unit_mix).reduce(
    (s, n) => s + n,
    0,
  );

  const metrics = [
    { label: "Height", value: `${option.height_m} m` },
    {
      label: "Gross Floor Area",
      value: `${option.total_gfa_m2.toLocaleString()} m²`,
    },
    {
      label: "Residential Units",
      value: totalResidential > 0 ? String(totalResidential) : "—",
    },
    { label: "Affordable Units", value: String(option.affordable_units) },
    {
      label: "Retail",
      value:
        option.retail_sqft > 0
          ? `${option.retail_sqft.toLocaleString()} sqft`
          : "None",
    },
  ];

  return (
    <div className="mt-4 animate-fade-in-up rounded-xl border-2 border-blue-200 bg-blue-50 p-5">
      {/* Header row */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-base font-bold text-blue-900">
            Option {idx + 1} — Selected Design
          </p>
          <p className="mt-0.5 text-xs text-blue-600">{option.massing_id}</p>
        </div>
        <span className="rounded-full bg-blue-600 px-3 py-1 text-xs font-bold uppercase tracking-wide text-white">
          Active
        </span>
      </div>

      {/* Key metrics grid */}
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
        {metrics.map(({ label, value }) => (
          <div
            key={label}
            className="rounded-lg border border-blue-100 bg-white px-3 py-2.5 shadow-sm"
          >
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
              {label}
            </p>
            <p className="mt-0.5 text-lg font-bold text-blue-800">{value}</p>
          </div>
        ))}
      </div>

      {/* Unit mix */}
      {Object.keys(option.unit_mix).length > 0 && (
        <div className="mt-3 border-t border-blue-100 pt-3">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-blue-700">
            Unit Mix
          </p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(option.unit_mix).map(([type, count]) => (
              <span
                key={type}
                className="rounded-full border border-blue-200 bg-white px-3 py-1 text-xs font-semibold text-blue-800"
              >
                {count}× {type}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 3D building render */}
      <BuildingViewer massingId={option.massing_id} />
    </div>
  );
}

// Renders the selected option's massing to interactive 3D HTML (server-side via
// the massing_generator render pipeline) and embeds it in an iframe. Re-renders
// whenever the selected option changes.
function BuildingViewer({ massingId }: { massingId: string }) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setUrl(null);
    setError(null);
    renderMassing(massingId)
      .then((r) => {
        if (!cancelled) {
          setUrl(`${BASE_URL}${r.html_url}`);
          setStatus("ready");
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e?.message ?? String(e));
          setStatus("error");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [massingId]);

  return (
    <div className="mt-3 border-t border-blue-100 pt-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-blue-700">
        3D Building
      </p>
      <div className="relative h-[420px] w-full overflow-hidden rounded-lg border border-blue-200 bg-slate-900">
        {status === "ready" && url && (
          <iframe
            key={url}
            src={url}
            title={`3D massing for ${massingId}`}
            className="h-full w-full border-0"
          />
        )}
        {status === "loading" && (
          <div className="flex h-full w-full items-center justify-center text-sm text-blue-200">
            Rendering 3D building…
          </div>
        )}
        {status === "error" && (
          <div className="flex h-full w-full items-center justify-center px-4 text-center text-sm text-red-300">
            Could not render 3D building: {error}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function BriefViewer({ brief }: { brief: BriefResponse }) {
  const env = brief.site_fundamentals;
  const con = brief.site_constraints;
  const fin = brief.financial_model;
  const approval = brief.approval_forecast;
  const opp = brief.community_response;
  const rec = brief.recommendation;
  const massingOptions = brief.design_options.options;

  const [selectedOption, setSelectedOption] = useState(0);

  // Animated values — longer durations make the count-up clearly visible
  const animApprovalPct = useCountUp(
    Math.round(approval.approval_probability * 100),
    1600,
  );
  const animIrr5y = useCountUp(fin.irr_5y * 100, 1600);
  const animCost = useCountUp(fin.construction_cost, 1800);
  const animConfidence = useCountUp(Math.round(rec.confidence * 100), 1400);
  const animApprovalPctExec = useCountUp(
    Math.round(approval.approval_probability * 100),
    1400,
  );

  // Recommendation colour scheme
  const recScheme = {
    buy: {
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      ring: "ring-2 ring-emerald-200",
      badge: "bg-emerald-600 text-white",
      heading: "text-emerald-900",
      body: "text-emerald-800",
      tag: "bg-emerald-100 text-emerald-700 border-emerald-200",
      label: "Strong acquisition candidate",
      subLabel: "This site is recommended for acquisition.",
    },
    conditional: {
      bg: "bg-amber-50",
      border: "border-amber-200",
      ring: "ring-2 ring-amber-200",
      badge: "bg-amber-500 text-white",
      heading: "text-amber-900",
      body: "text-amber-800",
      tag: "bg-amber-100 text-amber-700 border-amber-200",
      label: "Proceed with conditions",
      subLabel: "Acquisition is viable if key conditions are addressed.",
    },
    pass: {
      bg: "bg-slate-100",
      border: "border-slate-300",
      ring: "",
      badge: "bg-slate-700 text-white",
      heading: "text-slate-900",
      body: "text-slate-700",
      tag: "bg-slate-200 text-slate-600 border-slate-300",
      label: "Do not proceed",
      subLabel: "Current risk profile does not support acquisition.",
    },
  } as const;

  const scheme = recScheme[rec.recommendation];
  const approvalPct = Math.round(approval.approval_probability * 100);
  const risk = communityRisk(opp.expected_letter_count);

  // Approval narrative
  const approvalNarrative =
    approvalPct >= 70
      ? `At ${approvalPct}%, council approval is likely. The project has a strong majority position.`
      : approvalPct >= 50
        ? `At ${approvalPct}%, the vote is uncertain. A handful of councillors will determine the outcome.`
        : `At ${approvalPct}%, approval is unlikely without material changes to the application.`;

  return (
    <div className="space-y-4">
      {/* ── 1. Executive Summary ─────────────────────────────────────────── */}
      <div
        className={`animate-fade-in-up rounded-xl border ${scheme.border} ${scheme.bg} ${scheme.ring} p-6`}
        style={{ animationDelay: "0s" }}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <span
              className={`mt-0.5 shrink-0 rounded-lg px-3 py-1.5 text-sm font-bold uppercase tracking-wide ${scheme.badge}`}
            >
              {rec.recommendation}
            </span>
            <div>
              <p className={`text-xl font-bold leading-snug ${scheme.heading}`}>
                {scheme.label}
              </p>
              <p className={`mt-0.5 text-sm font-medium ${scheme.body}`}>
                {scheme.subLabel}
              </p>
              <p
                className={`mt-2 text-sm leading-relaxed ${scheme.body} opacity-90`}
              >
                {rec.rationale}
              </p>
            </div>
          </div>

          {/* Headline numbers — animated */}
          <div className="flex shrink-0 gap-8">
            <div className="text-right">
              <p className="text-3xl font-bold tabular-nums text-slate-900">
                {animConfidence.toFixed(0)}%
              </p>
              <p className="mt-0.5 text-xs text-slate-500">Confidence</p>
            </div>
            <div className="text-right">
              <p
                className={`text-3xl font-bold tabular-nums ${approvalColorClass(
                  approval.approval_probability,
                )}`}
              >
                {animApprovalPctExec.toFixed(0)}%
              </p>
              <p className="mt-0.5 text-xs text-slate-500">Approval prob.</p>
            </div>
          </div>
        </div>

        {rec.dominant_sensitivities.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className={`text-xs font-semibold ${scheme.body}`}>
              Key risks:
            </span>
            {rec.dominant_sensitivities.map((s) => (
              <span
                key={s}
                className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${scheme.tag}`}
              >
                {s}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── 2. Key metric cards — animated count-up ──────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {(
          [
            {
              label: "Approval probability",
              sub: "council vote",
              display: `${animApprovalPct.toFixed(0)}%`,
              colorClass: approvalColorClass(approval.approval_probability),
              delay: "0.05s",
            },
            {
              label: "IRR (5-year)",
              sub: "base case",
              display: `${animIrr5y.toFixed(1)}%`,
              colorClass: irrColorClass(fin.irr_5y),
              delay: "0.1s",
            },
            {
              label: "Max height",
              sub: `FSI ${env.max_fsi}`,
              display: `${env.max_height_m} m`,
              colorClass: "text-slate-900",
              delay: "0.15s",
            },
            {
              label: "Construction cost",
              sub: "est. total",
              display: fmtMoney(animCost),
              colorClass: "text-slate-900",
              delay: "0.2s",
            },
          ] as const
        ).map(({ label, sub, display, colorClass, delay }) => (
          <div
            key={label}
            className="animate-fade-in-up rounded-xl border border-slate-200 bg-white p-4 text-center shadow-sm transition-shadow duration-200 hover:shadow-md"
            style={{ animationDelay: delay }}
          >
            <p className={`text-2xl font-bold tabular-nums ${colorClass}`}>
              {display}
            </p>
            <p className="mt-0.5 text-xs font-semibold text-slate-600">
              {label}
            </p>
            <p className="text-xs text-slate-400">{sub}</p>
          </div>
        ))}
      </div>

      {/* ── 3. Approval forecast + Community response ─────────────────────── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Approval forecast */}
        <Card
          title="Approval Forecast"
          style={{ animation: "fadeInUp 0.45s ease-out 0.1s both" }}
        >
          <div className="space-y-5">
            {/* Why narrative */}
            <p className="rounded-lg bg-slate-50 px-3 py-2.5 text-sm text-slate-700">
              {approvalNarrative}
            </p>

            <AnimatedProbabilityBar
              probability={approval.approval_probability}
              label="approval probability"
            />

            {approval.swing_councillors.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Swing councillors
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {approval.swing_councillors.map((name) => (
                    <span
                      key={name}
                      className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800"
                    >
                      {name}
                    </span>
                  ))}
                </div>
                <p className="mt-1.5 text-xs text-slate-500">
                  These councillors have historically voted both ways on similar
                  applications — their votes are the deciding factor.
                </p>
              </div>
            )}

            {approval.levers.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Levers to improve approval
                </p>
                <ul className="space-y-2">
                  {approval.levers.map((lever) => (
                    <li
                      key={lever.change}
                      className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2.5 transition-colors duration-150 hover:bg-slate-100"
                    >
                      <span className="text-sm text-slate-700">
                        {lever.change}
                      </span>
                      <span className="ml-3 shrink-0 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
                        +{fmtPct(lever.delta_probability)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>

        {/* Community response */}
        <Card
          title="Community Response"
          style={{ animation: "fadeInUp 0.45s ease-out 0.15s both" }}
        >
          <div className="space-y-5">
            {/* Risk level + narrative */}
            <div className="flex items-start gap-3">
              <div className="shrink-0">
                <p className="text-3xl font-bold tabular-nums text-slate-900">
                  ~{opp.expected_letter_count}
                </p>
                <p className="text-xs text-slate-500">expected deputations</p>
              </div>
              <div className="flex-1">
                <span
                  className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${risk.bg} ${risk.color}`}
                >
                  {risk.label} opposition
                </span>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                  {risk.explanation}
                </p>
              </div>
            </div>

            {opp.organized_groups.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs text-slate-500">
                  Groups likely to organise
                </p>
                <div className="flex flex-wrap gap-1">
                  {opp.organized_groups.map((group) => (
                    <span
                      key={group}
                      className="rounded border border-red-100 bg-red-50 px-2 py-0.5 text-xs text-red-700"
                    >
                      {group}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {Object.keys(opp.top_concerns).length > 0 && (
              <div>
                <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Top concerns
                </p>
                <ul className="space-y-2.5">
                  {Object.entries(opp.top_concerns)
                    .sort(([, a], [, b]) => b - a)
                    .map(([concern, weight]) => (
                      <AnimatedConcernBar
                        key={concern}
                        concern={concern}
                        weight={weight}
                      />
                    ))}
                </ul>
              </div>
            )}

            {opp.mitigations.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Mitigations
                </p>
                <ul className="space-y-1.5">
                  {opp.mitigations.map((mitigation) => (
                    <li
                      key={mitigation}
                      className="flex items-start gap-2 text-sm text-slate-700"
                    >
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                      {mitigation}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {opp.sample_letters[0] && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Sample deputation letter
                </p>
                <blockquote className="max-h-36 overflow-y-auto rounded-lg border-l-4 border-red-300 bg-red-50 px-4 py-3 text-xs italic leading-relaxed text-red-800">
                  {opp.sample_letters[0].text}
                </blockquote>
                <p className="mt-1 text-right text-xs text-slate-400">
                  — {opp.sample_letters[0].source_neighborhood}
                </p>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* ── 4. Financial model ────────────────────────────────────────────── */}
      <Card
        title="Financial Model"
        style={{ animation: "fadeInUp 0.45s ease-out 0.2s both" }}
      >
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {[
            {
              label: "Construction cost",
              value: fmtMoney(fin.construction_cost),
            },
            {
              label: "Annual rent",
              value: fmtMoney(fin.projected_annual_rent),
            },
            {
              label: "Sale price",
              value: fin.projected_sale_price
                ? fmtMoney(fin.projected_sale_price)
                : "—",
            },
            { label: "Debt service", value: fmtMoney(fin.debt_service) },
            {
              label: "IRR (5y)",
              value: fmtPct(fin.irr_5y, 1),
              colorClass: irrColorClass(fin.irr_5y),
            },
            {
              label: "IRR (10y)",
              value: fmtPct(fin.irr_10y, 1),
              colorClass: irrColorClass(fin.irr_10y),
            },
          ].map(({ label, value, colorClass }) => (
            <div key={label} className="text-center">
              <p
                className={`text-xl font-bold ${colorClass ?? "text-slate-900"}`}
              >
                {value}
              </p>
              <p className="mt-0.5 text-xs text-slate-500">{label}</p>
            </div>
          ))}
        </div>

        {Object.keys(fin.sensitivities).length > 0 && (
          <div className="mt-5 border-t border-slate-100 pt-5">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Sensitivities
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="pb-2 text-left font-semibold text-slate-500">
                      Scenario
                    </th>
                    {Object.keys(Object.values(fin.sensitivities)[0] ?? {}).map(
                      (k) => (
                        <th
                          key={k}
                          className="pb-2 text-right font-semibold text-slate-500"
                        >
                          {k}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(fin.sensitivities).map(
                    ([scenario, metrics]) => (
                      <tr key={scenario} className="border-b border-slate-50">
                        <td className="py-1.5 text-slate-700">{scenario}</td>
                        {Object.values(metrics).map((v, idx) => (
                          <td
                            key={idx}
                            className="py-1.5 text-right font-mono text-slate-600"
                          >
                            {typeof v === "number" && v < 1 && v > -1
                              ? fmtPct(v, 1)
                              : fmtMoney(v)}
                          </td>
                        ))}
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>

      {/* ── 5. Site fundamentals + constraints ───────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card
          title="Site Fundamentals"
          style={{ animation: "fadeInUp 0.45s ease-out 0.25s both" }}
        >
          <dl className="space-y-3">
            {[
              { term: "Max height", detail: `${env.max_height_m} m` },
              { term: "Max FSI", detail: String(env.max_fsi) },
              {
                term: "Setbacks",
                detail:
                  Object.entries(env.setbacks)
                    .map(([dir, m]) => `${dir} ${m} m`)
                    .join(" · ") || "—",
              },
              {
                term: "Permitted uses",
                detail: env.permitted_uses.join(", ") || "—",
              },
              {
                term: "Parking minimum",
                detail:
                  env.parking_minimum !== null
                    ? `${env.parking_minimum} spaces`
                    : "No minimum",
              },
            ].map(({ term, detail }) => (
              <div
                key={term}
                className="flex items-start justify-between gap-4"
              >
                <dt className="shrink-0 text-sm font-medium text-slate-500">
                  {term}
                </dt>
                <dd className="text-right text-sm text-slate-800">{detail}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card
          title="Site Constraints"
          style={{ animation: "fadeInUp 0.45s ease-out 0.3s both" }}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500">
                Heritage status
              </span>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                  con.heritage_status === "designated"
                    ? "bg-red-100 text-red-700"
                    : con.heritage_status === "listed"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-slate-100 text-slate-600"
                }`}
              >
                {con.heritage_status}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500">
                Transit distance
              </span>
              <span className="text-sm text-slate-800">
                {con.transit_distance_m} m
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500">
                Tree canopy
              </span>
              <span className="text-sm text-slate-800">
                {con.tree_canopy_area_m2} m²
              </span>
            </div>

            {con.sun_shadow_rules.length > 0 && (
              <div>
                <p className="mb-1.5 text-sm font-medium text-slate-500">
                  Sun-shadow rules
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {con.sun_shadow_rules.map((rule) => (
                    <span
                      key={rule}
                      className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                    >
                      {rule}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {con.conservation_overlays.length > 0 && (
              <div>
                <p className="mb-1.5 text-sm font-medium text-slate-500">
                  Conservation overlays
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {con.conservation_overlays.map((overlay) => (
                    <span
                      key={overlay}
                      className="rounded border border-amber-100 bg-amber-50 px-2 py-0.5 text-xs text-amber-700"
                    >
                      {overlay}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {con.easements.length > 0 && (
              <div>
                <p className="mb-1.5 text-sm font-medium text-slate-500">
                  Easements
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {con.easements.map((easement) => (
                    <span
                      key={easement}
                      className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                    >
                      {easement}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* ── 6. Design options — interactive selectable cards ─────────────── */}
      {massingOptions.length > 0 && (
        <Card
          title="Design Options"
          style={{ animation: "fadeInUp 0.45s ease-out 0.35s both" }}
        >
          <p className="mb-4 text-sm text-slate-500">
            Click an option to see its full specification. The summary below
            updates immediately.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {massingOptions.map((option, idx) => {
              const isSelected = selectedOption === idx;
              return (
                <button
                  key={option.massing_id}
                  type="button"
                  onClick={() => setSelectedOption(idx)}
                  className={`rounded-xl border p-4 text-left transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-400 ${
                    isSelected
                      ? "scale-[1.02] border-blue-500 bg-blue-50 shadow-lg ring-2 ring-blue-200"
                      : "border-slate-200 bg-white hover:scale-[1.01] hover:border-slate-300 hover:shadow-sm"
                  }`}
                >
                  <div className="mb-3 flex items-center justify-between">
                    <p
                      className={`font-semibold ${
                        isSelected ? "text-blue-900" : "text-slate-800"
                      }`}
                    >
                      Option {idx + 1}
                    </p>
                    {isSelected && (
                      <span className="rounded-full bg-blue-600 px-2 py-0.5 text-xs font-bold text-white">
                        Selected
                      </span>
                    )}
                  </div>

                  <dl className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Height</dt>
                      <dd
                        className={`font-medium ${
                          isSelected ? "text-blue-800" : "text-slate-800"
                        }`}
                      >
                        {option.height_m} m
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">GFA</dt>
                      <dd
                        className={`font-medium ${
                          isSelected ? "text-blue-800" : "text-slate-800"
                        }`}
                      >
                        {option.total_gfa_m2.toLocaleString()} m²
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Affordable units</dt>
                      <dd
                        className={`font-medium ${
                          isSelected ? "text-blue-800" : "text-slate-800"
                        }`}
                      >
                        {option.affordable_units}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Retail</dt>
                      <dd
                        className={`font-medium ${
                          isSelected ? "text-blue-800" : "text-slate-800"
                        }`}
                      >
                        {option.retail_sqft.toLocaleString()} sqft
                      </dd>
                    </div>
                  </dl>

                  {Object.keys(option.unit_mix).length > 0 && (
                    <div className="mt-3 border-t border-slate-100 pt-3">
                      <p className="mb-1.5 text-xs font-medium text-slate-500">
                        Unit mix
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(option.unit_mix).map(
                          ([type, count]) => (
                            <span
                              key={type}
                              className={`rounded px-2 py-0.5 text-xs ${
                                isSelected
                                  ? "bg-blue-100 text-blue-700"
                                  : "bg-slate-100 text-slate-600"
                              }`}
                            >
                              {count} {type}
                            </span>
                          ),
                        )}
                      </div>
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Selected option summary — updates in-place when option changes */}
          {massingOptions[selectedOption] && (
            <SelectedOptionSummary
              option={massingOptions[selectedOption]}
              idx={selectedOption}
            />
          )}

          {/* Side-by-side comparison table (multi-option only) */}
          {massingOptions.length > 1 && (
            <DesignComparison
              options={massingOptions}
              selectedIdx={selectedOption}
            />
          )}
        </Card>
      )}
    </div>
  );
}
