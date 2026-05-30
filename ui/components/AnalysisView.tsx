"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import type { BriefResponse, ProjectOverrides } from "@/lib/api";
import { analyzeStream } from "@/lib/api";
import BriefViewer from "@/components/BriefViewer";
import SectionExportMenu from "@/components/export/SectionExportMenu";

// ─── agent definitions ────────────────────────────────────────────────────────

interface Agent {
  id: string;
  name: string;
  label: string;
  note: string;
  tasks: string[];
}

const AGENTS: Agent[] = [
  {
    id: "parcel",
    name: "Site Agent",
    label: "Reading Toronto parcel data",
    note: "Parcel geometry and land use loaded",
    tasks: [
      "Locating parcel in Open Data registry",
      "Extracting footprint polygon",
      "Resolving civic address",
    ],
  },
  {
    id: "zoning",
    name: "Zoning Agent",
    label: "Checking zoning envelope",
    note: "Max height, FSI, and setbacks resolved",
    tasks: [
      "Querying zoning bylaw spatial layer",
      "Computing FSI and height limits",
      "Resolving setback requirements",
    ],
  },
  {
    id: "constraints",
    name: "Constraints Agent",
    label: "Evaluating site constraints",
    note: "Heritage, canopy, and transit checked",
    tasks: [
      "Checking heritage register",
      "Measuring tree canopy coverage",
      "Computing transit proximity",
    ],
  },
  {
    id: "massing",
    name: "Massing Agent",
    label: "Generating massing options",
    note: "3D design candidates generated",
    tasks: [
      "Encoding envelope geometry",
      "Running massing generator",
      "Rendering facade options",
    ],
  },
  {
    id: "proforma",
    name: "Pro-Forma Agent",
    label: "Running financial pro-forma",
    note: "IRR, construction cost, and rents modelled",
    tasks: [
      "Loading CMHC rent comparables",
      "Estimating construction cost",
      "Computing IRR scenarios",
    ],
  },
  {
    id: "approval",
    name: "Approval Agent",
    label: "Forecasting council approval",
    note: "Vote probability and swing councillors scored",
    tasks: [
      "Encoding application features",
      "Running XGBoost classifier",
      "Identifying swing councillors",
    ],
  },
  {
    id: "community",
    name: "Community Agent",
    label: "Forecasting community response",
    note: "Opposition volume and concerns forecast",
    tasks: [
      "Embedding project description",
      "Retrieving similar deputations",
      "Generating sample letters",
    ],
  },
  {
    id: "principal",
    name: "Principal Agent",
    label: "Preparing recommendation",
    note: "Go / no-go decision and rationale written",
    tasks: [
      "Aggregating all agent outputs",
      "Computing confidence score",
      "Writing rationale",
    ],
  },
];

// Maps a backend graph node to the UI agent id(s) it completes. The first
// "Site Agent" (parcel) is satisfied once zoning resolves (both read the parcel).
const NODE_TO_UI: Record<string, string[]> = {
  zoning: ["parcel", "zoning"],
  constraints: ["constraints"],
  massing: ["massing"],
  proforma: ["proforma"],
  approvals: ["approval"],
  community: ["community"],
  principal: ["principal"],
};

// ─── types ────────────────────────────────────────────────────────────────────

type ApiResult =
  | { brief: BriefResponse; error: null }
  | { brief: null; error: string };

// ─── hooks ────────────────────────────────────────────────────────────────────

function useElapsedSeconds(): number {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => setSecs((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, []);
  return secs;
}

function useSubTaskCycle(activeAgentIdx: number): number {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    setIdx(0);
    const agent = AGENTS[activeAgentIdx];
    if (!agent) return;
    const interval = setInterval(
      () => setIdx((i) => (i + 1) % agent.tasks.length),
      1400
    );
    return () => clearInterval(interval);
  }, [activeAgentIdx]);
  return idx;
}

// ─── main component ───────────────────────────────────────────────────────────

export default function AnalysisView({
  parcelId,
  initialOverrides = {},
}: {
  parcelId: string;
  initialOverrides?: ProjectOverrides;
}) {
  const [completedCount, setCompletedCount] = useState(0);
  const completedRef = useRef(0);

  const [apiResult, setApiResult] = useState<ApiResult | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);
  const [briefVisible, setBriefVisible] = useState(false);

  // Applied project overrides — seeded from URL params (homepage scenario panel)
  // and updated by ScenarioControls after the brief loads.
  const [overrides, setOverrides] = useState<ProjectOverrides>(initialOverrides);
  const overridesKey = JSON.stringify(overrides);

  const doneRef = useRef<Set<string>>(new Set());

  const setCompleted = useCallback((n: number) => {
    completedRef.current = n;
    setCompletedCount(n);
  }, []);

  // Reset the progress flow whenever the scenario (parcel or overrides) changes.
  useEffect(() => {
    setApiResult(null);
    setShowSuccess(false);
    setBriefVisible(false);
    setCompleted(0);
    doneRef.current = new Set();
  }, [parcelId, overridesKey, setCompleted]);

  // Real progress: stream actual agent completions from the connector.
  useEffect(() => {
    doneRef.current = new Set();
    const cleanup = analyzeStream(parcelId, overrides, {
      onAgent: (node) => {
        (NODE_TO_UI[node] ?? []).forEach((id) => doneRef.current.add(id));
        setCompleted(AGENTS.filter((a) => doneRef.current.has(a.id)).length);
      },
      onBrief: (brief) => {
        setCompleted(AGENTS.length);
        setApiResult({ brief, error: null });
      },
      onError: (message) => setApiResult({ brief: null, error: message }),
    });
    return cleanup;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parcelId, overridesKey, setCompleted]);

  // Reveal: errors show immediately; a success result flashes the banner then the brief.
  useEffect(() => {
    if (!apiResult) return;
    if (apiResult.error) {
      setBriefVisible(true);
      return;
    }
    setShowSuccess(true);
    const t = setTimeout(() => setBriefVisible(true), 1500);
    return () => clearTimeout(t);
  }, [apiResult]);

  // ── render ──────────────────────────────────────────────────────────────────

  if (briefVisible) {
    if (apiResult?.error) {
      return <ErrorDisplay error={apiResult.error} />;
    }
    if (apiResult?.brief) {
      return (
        <div className="animate-fade-in space-y-4">
          {/* Brief action bar — export sits alongside the scenario controls */}
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-bold text-slate-900">Development Brief</h2>
            <SectionExportMenu
              brief={apiResult.brief}
              parcelId={parcelId}
              overrides={overrides}
            />
          </div>
          <ScenarioControls
            brief={apiResult.brief}
            applied={overrides}
            onRerun={setOverrides}
          />
          <BriefViewer brief={apiResult.brief} />
        </div>
      );
    }
  }

  if (showSuccess) {
    return <SuccessState parcelId={parcelId} />;
  }

  return <ProgressView completedCount={completedCount} parcelId={parcelId} />;
}

// ─── scenario controls (adjust & re-run) ──────────────────────────────────────

function ScenarioControls({
  brief,
  applied,
  onRerun,
}: {
  brief: BriefResponse;
  applied: ProjectOverrides;
  onRerun: (o: ProjectOverrides) => void;
}) {
  // `options` can legally be empty; fall back to zeroed defaults so the scenario
  // controls still render (and don't crash) when no base massing is available.
  const opt = brief.design_options.options[0] as
    | BriefResponse["design_options"]["options"][number]
    | undefined;
  const baseUnits = opt ? Object.values(opt.unit_mix).reduce((s, n) => s + n, 0) : 0;

  const [height, setHeight] = useState<number>(applied.height_m ?? opt?.height_m ?? 0);
  const [units, setUnits] = useState<number>(applied.total_units ?? baseUnits);
  const [affordable, setAffordable] = useState<number>(
    applied.affordable_units ?? opt?.affordable_units ?? 0
  );

  const isCustom = Object.keys(applied).length > 0;
  const fields: { label: string; value: number; set: (n: number) => void; step?: number }[] = [
    { label: "Height (m)", value: height, set: setHeight },
    { label: "Total units", value: units, set: setUnits },
    { label: "Affordable units", value: affordable, set: setAffordable },
  ];

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="mr-auto">
          <p className="text-sm font-semibold text-blue-900">Test your own scenario</p>
          <p className="text-xs text-blue-600">
            Adjust the building and re-run — approval, opposition and the score update.
          </p>
        </div>
        {fields.map(({ label, value, set }) => (
          <label key={label} className="flex flex-col gap-1">
            <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
              {label}
            </span>
            <input
              type="number"
              min={0}
              value={Number.isFinite(value) ? value : 0}
              onChange={(e) => set(Number(e.target.value))}
              className="w-24 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
          </label>
        ))}
        <button
          type="button"
          onClick={() =>
            onRerun({
              height_m: height,
              total_units: units,
              affordable_units: affordable,
            })
          }
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700"
        >
          Re-run scenario
        </button>
        {isCustom && (
          <button
            type="button"
            onClick={() => onRerun({})}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            Reset to auto
          </button>
        )}
      </div>
    </div>
  );
}

// ─── success state ────────────────────────────────────────────────────────────

function SuccessState({ parcelId }: { parcelId: string }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 py-12 animate-fade-in">
      <div className="flex w-full max-w-2xl flex-col items-center gap-6">

        {/* Animated green checkmark */}
        <div className="animate-scale-in flex h-20 w-20 items-center justify-center rounded-full bg-emerald-500 shadow-lg">
          <svg viewBox="0 0 40 40" className="h-10 w-10" aria-hidden="true">
            <polyline
              points="8,21 16,29 32,12"
              fill="none"
              stroke="white"
              strokeWidth="3.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="animate-check-draw"
            />
          </svg>
        </div>

        {/* Heading */}
        <div
          className="text-center animate-fade-in-up"
          style={{ animationDelay: "0.3s" }}
        >
          <p className="text-3xl font-bold text-slate-900">
            Development Brief Ready
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Parcel{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
              {parcelId}
            </code>
          </p>
        </div>

        {/* Completed pipeline card */}
        <div
          className="w-full animate-fade-in-up overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
          style={{ animationDelay: "0.45s" }}
        >
          {/* Card header */}
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
            <p className="text-sm font-semibold text-slate-700">
              Completed analysis pipeline
            </p>
            <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
              {AGENTS.length} / {AGENTS.length} complete
            </span>
          </div>

          {/* Agent grid — 1 col on mobile, 2 cols on sm+ */}
          {/* gap-px + bg-slate-100 creates hairline dividers between cells */}
          <div className="grid grid-cols-1 gap-px bg-slate-100 sm:grid-cols-2">
            {AGENTS.map((agent, i) => (
              <div
                key={agent.id}
                className="flex items-start gap-3 bg-white px-5 py-4 animate-fade-in-up"
                style={{ animationDelay: `${0.5 + i * 0.055}s` }}
              >
                {/* Check circle */}
                <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500">
                  <svg
                    viewBox="0 0 10 10"
                    className="h-2.5 w-2.5"
                    aria-hidden="true"
                  >
                    <polyline
                      points="2,5 4,7.5 8,2.5"
                      fill="none"
                      stroke="white"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>

                {/* Name + note */}
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-800">
                    {agent.name}
                  </p>
                  <p className="mt-0.5 text-xs leading-snug text-slate-400">
                    {agent.note}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Loading indicator */}
        <p
          className="animate-fade-in-up text-sm font-medium text-blue-600 animate-pulse"
          style={{ animationDelay: "1.0s" }}
        >
          Loading brief…
        </p>
      </div>
    </div>
  );
}

// ─── progress screen ──────────────────────────────────────────────────────────

function fmtElapsed(s: number): string {
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(
    s % 60
  ).padStart(2, "0")}`;
}

function ProgressView({
  completedCount,
  parcelId,
}: {
  completedCount: number;
  parcelId: string;
}) {
  const progressPct = Math.round((completedCount / AGENTS.length) * 100);
  const circumference = 2 * Math.PI * 36;
  const elapsed = useElapsedSeconds();
  const elapsedRef = useRef(0);
  elapsedRef.current = elapsed;

  const subTaskIdx = useSubTaskCycle(completedCount);

  return (
    <div className="flex flex-col items-center px-4 py-10">

      {/* ── Header ── */}
      <div className="mb-8 flex flex-col items-center gap-4 text-center">
        {/* Circular progress ring — larger and bolder */}
        <div className="relative h-[88px] w-[88px]">
          <svg className="-rotate-90" viewBox="0 0 80 80" width="88" height="88">
            <circle
              cx="40" cy="40" r="36"
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="6"
            />
            <circle
              cx="40" cy="40" r="36"
              fill="none"
              stroke={progressPct >= 100 ? "#10b981" : "#3b82f6"}
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - progressPct / 100)}
              style={{
                transition:
                  "stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.5s ease",
              }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-base font-bold text-slate-700">
              {progressPct}%
            </span>
          </div>
        </div>

        <div>
          <p className="text-2xl font-bold text-slate-900">
            Generating Development Brief
          </p>
          <p className="mt-1.5 text-sm text-slate-500">
            Parcel{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
              {parcelId}
            </code>
          </p>
          <div className="mt-2 flex items-center justify-center gap-3 text-xs text-slate-400">
            <span>
              {completedCount} of {AGENTS.length} agents complete
            </span>
            <span aria-hidden>·</span>
            <span className="font-mono tabular-nums">{fmtElapsed(elapsed)}</span>
          </div>
        </div>
      </div>

      {/* ── Agent cards ── */}
      <div className="w-full max-w-lg space-y-2">
        {AGENTS.map((agent, i) => {
          const isDone = i < completedCount;
          const isRunning = i === completedCount;
          const currentTask = agent.tasks[subTaskIdx] ?? agent.tasks[0];

          return (
            <div
              key={agent.id}
              className={`flex items-center gap-4 rounded-xl border px-5 py-3.5 transition-all duration-400 ${
                isRunning
                  ? "border-blue-300 bg-blue-50 shadow-md"
                  : isDone
                  ? "border-emerald-100 bg-white opacity-70"
                  : "border-transparent bg-white/40 opacity-25"
              }`}
            >
              {/* Status icon */}
              <div
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition-colors duration-500 ${
                  isDone
                    ? "bg-emerald-500"
                    : isRunning
                    ? "bg-blue-500"
                    : "bg-slate-200"
                }`}
              >
                {isDone ? (
                  <svg
                    viewBox="0 0 10 10"
                    className="h-3 w-3"
                    aria-hidden="true"
                  >
                    <polyline
                      points="2,5 4,7.5 8,2.5"
                      fill="none"
                      stroke="white"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : isRunning ? (
                  <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                )}
              </div>

              {/* Text */}
              <div className="min-w-0 flex-1">
                {/* Agent name row */}
                <div className="flex items-center gap-2">
                  <p
                    className={`text-sm font-bold leading-tight ${
                      isRunning
                        ? "text-blue-900"
                        : isDone
                        ? "text-slate-500"
                        : "text-slate-400"
                    }`}
                  >
                    {agent.name}
                  </p>
                  {isRunning && (
                    <span className="rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                      running
                    </span>
                  )}
                  {isDone && (
                    <span className="text-xs text-slate-400">{agent.label}</span>
                  )}
                </div>

                {/* Sub-task for the active agent */}
                {isRunning && (
                  <div className="mt-0.5">
                    <p
                      key={currentTask}
                      className="animate-fade-in-text text-xs text-blue-600"
                    >
                      {currentTask}…
                    </p>
                  </div>
                )}
              </div>

              {/* Spinner */}
              {isRunning && (
                <div className="shrink-0">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <p className="mt-5 text-xs text-slate-400">
        Running on GB10 · usually 30–90 s
      </p>
    </div>
  );
}

// ─── error screen ─────────────────────────────────────────────────────────────

function ErrorDisplay({ error }: { error: string }) {
  return (
    <div className="px-6 py-8">
      <div className="mx-auto max-w-lg rounded-xl border border-red-200 bg-red-50 p-6">
        <p className="font-semibold text-red-800">Failed to generate brief</p>
        <p className="mt-1 text-sm text-red-700">{error}</p>
        <p className="mt-3 text-sm text-red-600">
          Make sure the connector is running:
        </p>
        <code className="mt-1 block rounded bg-red-100 px-3 py-2 font-mono text-xs text-red-800">
          uv run uvicorn connector.api.main:app --reload --port 8000
        </code>
        <div className="mt-4">
          <Link
            href="/"
            className="inline-block rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700"
          >
            Try another parcel
          </Link>
        </div>
      </div>
    </div>
  );
}
