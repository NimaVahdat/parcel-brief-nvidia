"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import { DEMO_SITES, DemoSite, toParcelId } from "@/lib/demo-sites";

// ─── map (desktop only, loaded lazily) ───────────────────────────────────────

const ParcelMap = dynamic(() => import("@/components/ParcelMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-slate-100">
      <p className="text-xs text-slate-400">Loading map…</p>
    </div>
  ),
});

// ─── constants ────────────────────────────────────────────────────────────────

const CHIP_SITES = DEMO_SITES.slice(0, 5) as readonly DemoSite[];

const AGENTS = [
  "Site Agent",
  "Zoning Agent",
  "Constraints Agent",
  "Massing Agent",
  "Pro-Forma Agent",
  "Approval Agent",
  "Community Agent",
] as const;

// ─── animation variants ───────────────────────────────────────────────────────

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1, delayChildren: 0.08 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] as const },
  },
};

// ─── sub-components ───────────────────────────────────────────────────────────

function AgentActivityCard({ runningIdx }: { runningIdx: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.6, delay: 0.9, ease: [0.22, 1, 0.36, 1] }}
      className="glass-card absolute right-4 top-4 w-52 rounded-2xl p-4"
    >
      {/* Header */}
      <div className="mb-3 flex items-center gap-2">
        <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
        <span className="text-xs font-bold text-slate-800">Live Analysis</span>
        <span className="ml-auto rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">
          Preview
        </span>
      </div>

      {/* Agent rows */}
      <div className="space-y-1.5">
        {AGENTS.map((name, i) => {
          const isDone = i < runningIdx;
          const isRunning = i === runningIdx;
          return (
            <div key={name} className="flex items-center gap-2">
              {/* Status dot / check */}
              <div className="flex h-4 w-4 shrink-0 items-center justify-center">
                {isDone ? (
                  <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-emerald-500">
                    <svg viewBox="0 0 8 8" className="h-2 w-2" fill="none">
                      <polyline
                        points="1.5,4 3,5.5 6.5,2"
                        stroke="white"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                ) : isRunning ? (
                  <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-blue-500" />
                ) : (
                  <span className="h-2 w-2 rounded-full bg-slate-200" />
                )}
              </div>

              {/* Agent name */}
              <span
                className={`flex-1 text-[11px] leading-none ${
                  isDone
                    ? "text-slate-400"
                    : isRunning
                    ? "font-semibold text-blue-700"
                    : "text-slate-300"
                }`}
              >
                {name}
              </span>

              {isRunning && (
                <span className="animate-pulse text-[10px] font-semibold text-blue-500">
                  ···
                </span>
              )}
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

function BriefPreviewCard() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 1.1, ease: [0.22, 1, 0.36, 1] }}
      className="glass-card animate-float absolute bottom-4 left-4 w-56 rounded-2xl p-4"
    >
      {/* Address */}
      <div className="mb-3 flex items-start gap-2">
        <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
        <div>
          <p className="text-[11px] font-bold leading-tight text-slate-800">
            720 King St W
          </p>
          <p className="text-[10px] text-slate-400">Entertainment District</p>
        </div>
        <span className="ml-auto rounded-md bg-emerald-100 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-emerald-700">
          BUY
        </span>
      </div>

      {/* Metrics grid */}
      <div className="mb-3 grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-2.5">
        {(
          [
            ["Zoning", "Mixed-Use"],
            ["Height", "45 m"],
            ["FSI", "4.5"],
            ["IRR (5y)", "14.2%"],
          ] as const
        ).map(([label, val]) => (
          <div key={label}>
            <p className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">
              {label}
            </p>
            <p className="text-xs font-bold text-slate-800">{val}</p>
          </div>
        ))}
      </div>

      {/* Approval bar */}
      <div className="mb-3">
        <div className="mb-1 flex justify-between">
          <span className="text-[10px] font-medium text-slate-500">
            Council approval
          </span>
          <span className="text-[10px] font-bold text-emerald-500">73%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div className="h-1.5 w-[73%] rounded-full bg-emerald-500" />
        </div>
      </div>

      {/* Confidence */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-400">Confidence</span>
        <span className="text-[10px] font-bold text-slate-700">82%</span>
      </div>

      <p className="mt-2 text-center text-[9px] text-slate-300">
        Sample brief · Demo data
      </p>
    </motion.div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function HeroSection() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [noMatch, setNoMatch] = useState(false);
  const [isLg, setIsLg] = useState(false);
  const [runningIdx, setRunningIdx] = useState(2);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Detect desktop breakpoint
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    setIsLg(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsLg(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Cycle AI agent "running" indicator
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setRunningIdx((prev) => (prev + 1) % AGENTS.length);
    }, 1800);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim().toLowerCase();
    if (!q) return;
    const match = DEMO_SITES.find((s) => s.address.toLowerCase().includes(q));
    if (match) {
      setNoMatch(false);
      router.push(
        `/analyze/${encodeURIComponent(toParcelId(match.lat, match.lng))}`
      );
    } else {
      setNoMatch(true);
    }
  }

  function handleChipClick(site: DemoSite) {
    router.push(
      `/analyze/${encodeURIComponent(toParcelId(site.lat, site.lng))}`
    );
  }

  return (
    <section className="relative flex flex-col overflow-hidden bg-slate-50 lg:flex-row lg:h-[calc(100vh-52px)]">
      {/* Decorative layers */}
      <div aria-hidden className="bg-grid pointer-events-none absolute inset-0" />
      <div aria-hidden className="hero-glow pointer-events-none absolute inset-0" />

      {/* ── Left column: content ─────────────────────────────────────────── */}
      <div className="relative z-10 flex w-full flex-col justify-center px-8 py-16 lg:w-[54%] lg:border-r lg:border-slate-200 lg:px-14 xl:px-20">
        <motion.div variants={stagger} initial="hidden" animate="show">

          {/* Eyebrow */}
          <motion.div variants={fadeUp} className="mb-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-blue-700">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
              AI Co-Pilot · Toronto Real Estate
            </span>
          </motion.div>

          {/* Headline */}
          <motion.h1
            variants={fadeUp}
            className="text-[2.6rem] font-extrabold leading-[1.07] tracking-tight text-slate-900 sm:text-5xl lg:text-[3.1rem] xl:text-[3.5rem]"
          >
            Site analysis in
            <br />
            <span className="text-blue-600">60 seconds.</span>
            <br />
            Not 6 weeks.
          </motion.h1>

          {/* Sub-headline */}
          <motion.p
            variants={fadeUp}
            className="mt-6 max-w-lg text-base leading-relaxed text-slate-600 sm:text-lg"
          >
            AutoSite analyzes any Toronto parcel and returns a decision-grade
            development brief — zoning, massing, financials, council approval
            odds, and community forecast. Powered by{" "}
            <span className="font-semibold text-slate-800">
              8 AI agents on NVIDIA GB10.
            </span>
          </motion.p>

          {/* Primary CTA — address search */}
          <motion.div variants={fadeUp} className="mt-9">
            <form
              onSubmit={handleSearch}
              className="flex flex-col gap-3 sm:flex-row"
            >
              <input
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setNoMatch(false);
                }}
                placeholder="Enter a Toronto address — e.g. 720 King St W"
                className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-5 py-3.5 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 sm:text-base"
              />
              <button
                type="submit"
                className="shrink-0 rounded-xl bg-blue-600 px-7 py-3.5 text-sm font-semibold text-white shadow-sm transition-colors duration-150 hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400 sm:text-base"
              >
                Analyze →
              </button>
            </form>

            {noMatch && (
              <p className="mt-2 text-sm text-red-600">
                Address not found — try one of the demo sites below.
              </p>
            )}
          </motion.div>

          {/* Demo chips */}
          <motion.div
            variants={fadeUp}
            className="mt-4 flex flex-wrap items-center gap-2"
          >
            <span className="text-xs text-slate-400">Try:</span>
            {CHIP_SITES.map((site) => (
              <button
                key={site.address}
                type="button"
                onClick={() => handleChipClick(site)}
                className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 shadow-sm transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
              >
                {site.address.split(",")[0]}
              </button>
            ))}
          </motion.div>

          {/* Divider + secondary CTA */}
          <motion.div variants={fadeUp} className="mt-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-slate-200" />
            <span className="text-xs text-slate-400">or</span>
            <div className="h-px flex-1 bg-slate-200" />
          </motion.div>
          <motion.div variants={fadeUp} className="mt-3 text-center lg:text-left">
            <a
              href="#features"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition-colors hover:text-blue-600"
            >
              {isLg
                ? "Click any parcel on the map →"
                : "See what's in the brief ↓"}
            </a>
          </motion.div>

        </motion.div>
      </div>

      {/* ── Right column: interactive map (desktop only) ──────────────────── */}
      {isLg && (
        <div className="relative w-[46%]">
          {/* Map fills the column */}
          <div className="absolute inset-0">
            <ParcelMap />
          </div>

          {/* Floating glass cards — z above Leaflet controls */}
          <div className="pointer-events-none absolute inset-0 z-[1001]">
            <AgentActivityCard runningIdx={runningIdx} />
            <BriefPreviewCard />
          </div>
        </div>
      )}
    </section>
  );
}
