"use client";

import { useState, useEffect, Fragment } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import dynamic from "next/dynamic";
import { DEMO_SITES, DemoSite, toParcelId } from "@/lib/demo-sites";
import ScenarioPanel, {
  ScenarioValues,
  SCENARIO_DEFAULTS,
} from "@/components/landing/ScenarioPanel";

// ─── map — loaded lazily, rendered only on desktop ────────────────────────────

const ParcelMap = dynamic(() => import("@/components/ParcelMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-slate-100">
      <p className="text-xs text-slate-400">Loading map…</p>
    </div>
  ),
});

// ─── constants ────────────────────────────────────────────────────────────────

const CHIP_SITES = DEMO_SITES.slice(0, 3) as readonly DemoSite[];

// ─── animation variants ───────────────────────────────────────────────────────

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08, delayChildren: 0.04 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.48, ease: [0.22, 1, 0.36, 1] as const },
  },
};

// ─── workflow strip ───────────────────────────────────────────────────────────

const WORKFLOW = [
  {
    label: "Select parcel",
    iconBg: "bg-blue-50",
    iconColor: "text-blue-600",
    d: "M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z",
  },
  {
    label: "Zoning & site",
    iconBg: "bg-slate-100",
    iconColor: "text-slate-500",
    d: "M7.5 3.75H6A2.25 2.25 0 0 0 3.75 6v1.5M16.5 3.75H18A2.25 2.25 0 0 1 20.25 6v1.5m0 9V18A2.25 2.25 0 0 1 18 20.25h-1.5m-9 0H6A2.25 2.25 0 0 1 3.75 18v-1.5M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
  },
  {
    label: "3D massing",
    iconBg: "bg-violet-50 dark:bg-violet-950",
    iconColor: "text-violet-600 dark:text-violet-400",
    d: "M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9",
  },
  {
    label: "Financial model",
    iconBg: "bg-emerald-50 dark:bg-emerald-950",
    iconColor: "text-emerald-600 dark:text-emerald-400",
    d: "M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 0 1 5.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941",
  },
  {
    label: "Approval odds",
    iconBg: "bg-amber-50 dark:bg-amber-950",
    iconColor: "text-amber-600 dark:text-amber-400",
    d: "M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z",
  },
  {
    label: "Go / No-Go",
    iconBg: "bg-emerald-100 dark:bg-emerald-950",
    iconColor: "text-emerald-700 dark:text-emerald-400",
    d: "M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z",
  },
] as const;

type WorkflowStep = (typeof WORKFLOW)[number];

function WorkflowChip({
  step,
  index,
}: {
  step: WorkflowStep;
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.08 + index * 0.07, ease: "easeOut" }}
      className="flex w-[130px] shrink-0 flex-col items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm"
    >
      {/* Step number */}
      <span className="text-xs font-bold tabular-nums text-slate-400">
        {String(index + 1).padStart(2, "0")}
      </span>

      {/* Icon */}
      <span
        className={`flex h-12 w-12 items-center justify-center rounded-xl ${step.iconBg}`}
      >
        <svg
          viewBox="0 0 24 24"
          className={`h-7 w-7 ${step.iconColor}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d={step.d} />
        </svg>
      </span>

      {/* Label */}
      <span className="text-center text-xs font-semibold leading-tight text-slate-700">
        {step.label}
      </span>
    </motion.div>
  );
}

function WorkflowArrow() {
  return (
    <svg
      viewBox="0 0 16 16"
      className="h-4 w-4 shrink-0 text-slate-400"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M6.22 3.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L9.94 8 6.22 4.28a.75.75 0 0 1 0-1.06Z" />
    </svg>
  );
}

function WorkflowStrip() {
  return (
    <div className="flex items-center justify-center gap-2">
      {WORKFLOW.map((step, i) => (
        <Fragment key={step.label}>
          {i > 0 && <WorkflowArrow />}
          <WorkflowChip step={step} index={i} />
        </Fragment>
      ))}
    </div>
  );
}

// ─── component ────────────────────────────────────────────────────────────────

export default function HeroSection() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [noMatch, setNoMatch] = useState(false);
  const [isLg, setIsLg] = useState(false);
  const [scenario, setScenario] = useState<ScenarioValues>(SCENARIO_DEFAULTS);
  const [showScenario, setShowScenario] = useState(false);
  // Must be explicitly turned ON before custom values are included in the URL.
  const [useCustomScenario, setUseCustomScenario] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    setIsLg(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsLg(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  function analyzeUrl(lat: number, lng: number): string {
    const parcelId = toParcelId(lat, lng);
    // Custom values are ONLY sent when the user has explicitly enabled the toggle.
    if (!useCustomScenario) {
      return `/analyze/${encodeURIComponent(parcelId)}`;
    }
    const p = new URLSearchParams({
      height_m: String(scenario.height_m),
      total_units: String(scenario.total_units),
      affordable_units: String(scenario.affordable_units),
    });
    return `/analyze/${encodeURIComponent(parcelId)}?${p.toString()}`;
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim().toLowerCase();
    if (!q) return;
    const match = DEMO_SITES.find((s) => s.address.toLowerCase().includes(q));
    if (match) {
      setNoMatch(false);
      router.push(analyzeUrl(match.lat, match.lng));
    } else {
      setNoMatch(true);
    }
  }

  function handleChipClick(site: DemoSite) {
    router.push(analyzeUrl(site.lat, site.lng));
  }

  return (
    <section className="relative overflow-hidden bg-slate-50">
      <div aria-hidden className="bg-grid pointer-events-none absolute inset-0" />
      <div aria-hidden className="hero-glow pointer-events-none absolute inset-0" />

      <div className="relative z-10 mx-auto flex max-w-7xl flex-col gap-10 px-6 py-8 lg:flex-row lg:items-center lg:gap-10 lg:px-8 lg:py-10 xl:px-16">

        {/* ── Left column ──────────────────────────────────────────────────── */}
        <motion.div
          className="min-w-0 flex-1"
          variants={stagger}
          initial="hidden"
          animate="show"
        >
          {/* Headline */}
          <motion.h1
            variants={fadeUp}
            className="text-3xl font-black leading-[1.4] tracking-normal text-slate-900 sm:text-4xl lg:text-[2.25rem] xl:text-5xl"
          >
            Development briefs
            <br />
            <span className="text-blue-600">in minutes,</span>
            <br />
            not months.
          </motion.h1>

          {/* Address search — no label, no divider */}
          <motion.div variants={fadeUp} className="mt-8">
            <form
              onSubmit={handleSearch}
              className="flex flex-col gap-2.5 sm:flex-row"
            >
              <input
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setNoMatch(false);
                }}
                placeholder="Enter a Toronto address — e.g. 720 King St W"
                className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3.5 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
              <button
                type="submit"
                className="shrink-0 rounded-xl bg-blue-600 px-7 py-3.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                Analyze →
              </button>
            </form>

            {noMatch && (
              <p className="mt-1.5 text-sm text-red-600">
                Address not found — try one of the examples below.
              </p>
            )}

            {/* Demo chips */}
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {CHIP_SITES.map((site) => (
                <button
                  key={site.address}
                  type="button"
                  onClick={() => handleChipClick(site)}
                  className="cursor-pointer rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500 shadow-sm transition-all duration-150 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 hover:shadow focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-1"
                >
                  {site.address.split(",")[0]}
                </button>
              ))}
            </div>
          </motion.div>

          {/* Scenario toggle — collapsed by default */}
          <motion.div variants={fadeUp} className="mt-5">
            <button
              type="button"
              onClick={() => setShowScenario((v) => !v)}
              className="flex cursor-pointer items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-medium text-blue-700 shadow-sm transition-all duration-150 hover:bg-blue-100 hover:border-blue-300 hover:text-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
            >
              <svg
                viewBox="0 0 12 12"
                className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${
                  showScenario ? "rotate-90" : ""
                }`}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M4 2l4 4-4 4" />
              </svg>
              Customize scenario assumptions
              {/* Badge visible when active but panel is collapsed */}
              {useCustomScenario && !showScenario && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
                  Active
                </span>
              )}
            </button>

            <AnimatePresence initial={false}>
              {showScenario && (
                <motion.div
                  key="scenario"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.22, ease: "easeInOut" }}
                  className="overflow-hidden"
                >
                  <div className="pt-3">
                    <ScenarioPanel
                      values={scenario}
                      onChange={setScenario}
                      enabled={useCustomScenario}
                      onToggle={() => setUseCustomScenario((v) => !v)}
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </motion.div>

        {/* ── Right column: map (desktop only) ────────────────────────────── */}
        {isLg && (
          <div className="shrink-0 lg:w-[560px] xl:w-[660px]">
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden rounded-2xl border border-slate-200 shadow-lg"
              style={{ height: 600 }}
            >
              <ParcelMap />
            </motion.div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.6 }}
              className="mt-2.5 text-center text-sm font-medium text-slate-500"
            >
              Click any parcel to start an analysis
            </motion.p>
          </div>
        )}
      </div>

      {/* ── Full-width workflow strip ─────────────────────────────────────── */}
      <div className="relative z-10 border-t border-slate-200 px-6 py-5 lg:px-8 xl:px-16">
        <WorkflowStrip />
      </div>
    </section>
  );
}
