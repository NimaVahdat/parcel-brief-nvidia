"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import { DEMO_SITES, DemoSite, toParcelId } from "@/lib/demo-sites";

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

// Three representative Toronto addresses — enough for a demo without clutter.
const CHIP_SITES = DEMO_SITES.slice(0, 3) as readonly DemoSite[];

// ─── animation variants ───────────────────────────────────────────────────────

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.09, delayChildren: 0.04 } },
};

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.48, ease: [0.22, 1, 0.36, 1] as const },
  },
};

// ─── component ────────────────────────────────────────────────────────────────

export default function HeroSection() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [noMatch, setNoMatch] = useState(false);
  const [isLg, setIsLg] = useState(false);

  // Detect desktop breakpoint — map is rendered only when this is true.
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    setIsLg(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsLg(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
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
    <section className="relative overflow-hidden bg-slate-50">
      {/* Decorative background layers */}
      <div aria-hidden className="bg-grid pointer-events-none absolute inset-0" />
      <div aria-hidden className="hero-glow pointer-events-none absolute inset-0" />

      <div className="relative z-10 mx-auto flex max-w-7xl flex-col gap-10 px-6 py-16 lg:flex-row lg:items-center lg:gap-10 lg:px-8 lg:py-20 xl:px-16">

        {/* ── Left column: value prop + search (primary) ─────────────────── */}
        <motion.div
          className="min-w-0 flex-1"
          variants={stagger}
          initial="hidden"
          animate="show"
        >
          {/* Headline — no eyebrow, starts immediately with the claim */}
          <motion.h1
            variants={fadeUp}
            className="text-4xl font-extrabold leading-[1.07] tracking-tight text-slate-900 sm:text-5xl lg:text-[2.75rem] xl:text-6xl"
          >
            Development briefs
            <br />
            <span className="text-blue-600">in minutes,</span>
            <br />
            not months.
          </motion.h1>

          {/* Sub-headline — icon workflow strip */}
          <motion.div
            variants={fadeUp}
            className="mt-6 flex flex-wrap items-center gap-x-2 gap-y-3"
          >
            {/* Step 1 */}
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 shadow-sm">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-blue-100 text-sm">
                📍
              </span>
              <span className="text-sm font-semibold text-slate-700">Pick a parcel</span>
            </div>

            <span className="text-slate-300 text-lg font-light">→</span>

            {/* Step 2 */}
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 shadow-sm">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-100 text-sm">
                ⚡
              </span>
              <span className="text-sm font-semibold text-slate-700">AI analysis</span>
            </div>

            <span className="text-slate-300 text-lg font-light">→</span>

            {/* Step 3 */}
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 shadow-sm">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-emerald-100 text-sm">
                ✓
              </span>
              <span className="text-sm font-semibold text-slate-700">Brief in 60 s</span>
            </div>
          </motion.div>

          {/* Divider */}
          <motion.div
            variants={fadeUp}
            className="my-7 h-px bg-slate-200"
          />

          {/* Address search */}
          <motion.div variants={fadeUp}>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Enter a Toronto address to start
            </p>
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
                placeholder="e.g. 720 King St W, Toronto"
                className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
              <button
                type="submit"
                className="shrink-0 rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                Analyze →
              </button>
            </form>

            {noMatch && (
              <p className="mt-1.5 text-sm text-red-600">
                Address not found — try one of the demo sites below.
              </p>
            )}

            {/* Demo chips — 3 addresses */}
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-slate-400">Try:</span>
              {CHIP_SITES.map((site) => (
                <button
                  key={site.address}
                  type="button"
                  onClick={() => handleChipClick(site)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-sm transition-all hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 hover:shadow"
                >
                  {site.address.split(",")[0]}
                </button>
              ))}
            </div>
          </motion.div>

          {/* Secondary CTA — context-aware */}
          <motion.div variants={fadeUp} className="mt-5">
            {isLg ? (
              // Desktop: map is right there, no scroll needed
              <p className="text-sm text-slate-400">
                or click any parcel on the map →
              </p>
            ) : (
              // Mobile: map is in the section below
              <a
                href="#map-section"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition-colors hover:text-blue-600"
              >
                or explore on map
                <span className="animate-bounce">↓</span>
              </a>
            )}
          </motion.div>
        </motion.div>

        {/* ── Right column: compact map + brief caption (desktop only) ───── */}
        {isLg && (
          <div className="shrink-0 lg:w-[480px] xl:w-[560px]">
            {/* Map panel */}
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden rounded-2xl border border-slate-200 shadow-lg"
              style={{ height: 440 }}
            >
              <ParcelMap />
            </motion.div>

            {/* Brief caption strip — minimal sample output */}
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.55 }}
              className="glass-card mt-2.5 rounded-xl px-4 py-2.5"
            >
              <div className="flex items-center gap-2.5">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
                <span className="text-xs font-medium text-slate-700">
                  720 King St W, Toronto
                </span>
                <span className="shrink-0 rounded-md bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-700">
                  BUY
                </span>
                <span className="ml-auto shrink-0 font-mono text-[11px] text-slate-400">
                  IRR 14.2% · 73%
                </span>
              </div>
            </motion.div>

            {/* Click instruction */}
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.75 }}
              className="mt-1.5 text-center text-[11px] text-slate-400"
            >
              Click any parcel to start an analysis
            </motion.p>
          </div>
        )}
      </div>
    </section>
  );
}
