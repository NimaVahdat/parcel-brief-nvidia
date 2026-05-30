"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import type { BriefResponse } from "@/lib/api";
import { analyze } from "@/lib/api";
import BriefViewer from "@/components/BriefViewer";

// ─── analysis stages ─────────────────────────────────────────────────────────

const STAGES = [
  {
    label: "Analyzing zoning regulations",
    detail: "Loading Toronto Open Data parcel and zoning layers",
  },
  {
    label: "Evaluating site constraints",
    detail: "Checking heritage status, tree canopy, and transit access",
  },
  {
    label: "Generating design options",
    detail: "Fitting 3D massing candidates to the legal envelope",
  },
  {
    label: "Running financial model",
    detail: "Projecting IRR, rents, construction cost, and debt service",
  },
  {
    label: "Predicting council approval",
    detail: "Scoring application against Toronto vote history",
  },
  {
    label: "Forecasting community response",
    detail: "Retrieving neighbourhood deputation patterns",
  },
  {
    label: "Preparing recommendation",
    detail: "Synthesizing brief and go / no-go decision",
  },
];

// Cumulative ms at which each stage transitions (simulated pacing).
// The last stage never auto-advances — it waits for the real API response.
const STAGE_CUMULATIVE_MS = [4500, 10000, 18000, 26000, 35000, 43000];

// ─── types ───────────────────────────────────────────────────────────────────

type ApiResult =
  | { brief: BriefResponse; error: null }
  | { brief: null; error: string };

// ─── main component ───────────────────────────────────────────────────────────

export default function AnalysisView({ parcelId }: { parcelId: string }) {
  // Number of stages that have completed (0 = none, STAGES.length = all done)
  const [completedCount, setCompletedCount] = useState(0);
  const completedRef = useRef(0); // mirror state in a ref so callbacks stay current

  const [apiResult, setApiResult] = useState<ApiResult | null>(null);
  const [briefVisible, setBriefVisible] = useState(false);
  const timerIdsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Stable setter that keeps the ref in sync
  const setCompleted = useCallback((n: number) => {
    completedRef.current = n;
    setCompletedCount(n);
  }, []); // setCompletedCount from useState is unconditionally stable

  // Simulated progress advance
  useEffect(() => {
    const ids = STAGE_CUMULATIVE_MS.map((ms, i) =>
      setTimeout(() => setCompleted(i + 1), ms)
    );
    timerIdsRef.current = ids;
    return () => ids.forEach(clearTimeout);
  }, [setCompleted]);

  // Real API fetch
  useEffect(() => {
    analyze(parcelId)
      .then((brief) => setApiResult({ brief, error: null }))
      .catch((e) =>
        setApiResult({ brief: null, error: (e as Error).message })
      );
  }, [parcelId]);

  // When API resolves: cancel remaining simulated timers, rapidly complete
  // any outstanding stages, then reveal the brief.
  useEffect(() => {
    if (!apiResult) return;

    // Cancel pending simulated advances
    timerIdsRef.current.forEach(clearTimeout);

    const start = completedRef.current;
    const remaining = STAGES.length - start;
    const rapidMs = 230;

    for (let i = 0; i < remaining; i++) {
      const n = start + i + 1;
      setTimeout(() => setCompleted(n), i * rapidMs);
    }
    setTimeout(() => setBriefVisible(true), remaining * rapidMs + 380);
  }, [apiResult, setCompleted]);

  // ── render ──────────────────────────────────────────────────────────────────

  if (briefVisible) {
    if (apiResult?.error) {
      return <ErrorDisplay error={apiResult.error} />;
    }
    if (apiResult?.brief) {
      return (
        <div className="animate-fade-in">
          <BriefViewer brief={apiResult.brief} />
        </div>
      );
    }
  }

  return <ProgressView completedCount={completedCount} parcelId={parcelId} />;
}

// ─── progress screen ──────────────────────────────────────────────────────────

function ProgressView({
  completedCount,
  parcelId,
}: {
  completedCount: number;
  parcelId: string;
}) {
  const progressPct = Math.round((completedCount / STAGES.length) * 100);
  const circumference = 2 * Math.PI * 24;

  return (
    <div className="flex flex-col items-center px-6 py-14">
      {/* Circular progress + heading */}
      <div className="mb-10 text-center">
        <div className="mb-5 flex justify-center">
          <div className="relative h-16 w-16">
            <svg
              className="-rotate-90"
              viewBox="0 0 56 56"
              width="64"
              height="64"
            >
              {/* track */}
              <circle
                cx="28"
                cy="28"
                r="24"
                fill="none"
                stroke="#e2e8f0"
                strokeWidth="4"
              />
              {/* progress arc */}
              <circle
                cx="28"
                cy="28"
                r="24"
                fill="none"
                stroke="#3b82f6"
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={circumference * (1 - progressPct / 100)}
                style={{ transition: "stroke-dashoffset 0.6s ease" }}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-sm font-bold text-slate-700">
                {progressPct}%
              </span>
            </div>
          </div>
        </div>

        <p className="text-xl font-bold text-slate-900">
          Generating Development Brief
        </p>
        <p className="mt-1.5 text-sm text-slate-500">
          Parcel{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
            {parcelId}
          </code>
        </p>
        <p className="mt-1 text-xs text-slate-400">
          This usually takes 30–90 seconds
        </p>
      </div>

      {/* Stage list */}
      <div className="w-full max-w-md space-y-1.5">
        {STAGES.map((stage, i) => {
          const isCompleted = i < completedCount;
          const isActive = i === completedCount;

          return (
            <div
              key={stage.label}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 transition-all duration-300 ${
                isActive
                  ? "border border-blue-200 bg-blue-50 shadow-sm"
                  : isCompleted
                  ? "bg-slate-50 opacity-70"
                  : "opacity-30"
              }`}
            >
              {/* Status icon */}
              <div
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-colors duration-300 ${
                  isCompleted
                    ? "bg-emerald-500"
                    : isActive
                    ? "bg-blue-500"
                    : "bg-slate-200"
                }`}
              >
                {isCompleted ? (
                  <svg viewBox="0 0 10 10" className="h-3 w-3">
                    <polyline
                      points="2,5 4,7.5 8,2.5"
                      fill="none"
                      stroke="white"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : isActive ? (
                  <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                )}
              </div>

              {/* Label */}
              <div className="min-w-0 flex-1">
                <p
                  className={`text-sm font-medium ${
                    isActive
                      ? "text-blue-900"
                      : isCompleted
                      ? "text-slate-500 line-through decoration-slate-300"
                      : "text-slate-400"
                  }`}
                >
                  {stage.label}
                </p>
                {isActive && (
                  <p className="mt-0.5 text-xs text-blue-600">{stage.detail}</p>
                )}
              </div>

              {/* Spinner for active stage */}
              {isActive && (
                <div className="ml-auto shrink-0">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-200 border-t-blue-500" />
                </div>
              )}
            </div>
          );
        })}
      </div>
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
