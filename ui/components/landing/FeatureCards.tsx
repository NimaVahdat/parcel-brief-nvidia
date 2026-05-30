"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";

// ─── data ─────────────────────────────────────────────────────────────────────

type Accent = "blue" | "violet" | "emerald" | "amber" | "rose" | "slate";

interface Feature {
  step: string;
  title: string;
  description: string;
  metric: string;
  accent: Accent;
  iconPath: string;
}

const FEATURES: Feature[] = [
  {
    step: "01",
    title: "Legal Building Envelope",
    description:
      "Max height, FSI, setbacks, permitted uses, and parking minimums resolved from Toronto's zoning bylaw spatial layer.",
    metric: "Max 45 m · FSI 4.5 · 3 m setbacks",
    accent: "blue",
    iconPath:
      "M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 10v11M12 10v11M16 10v11",
  },
  {
    step: "02",
    title: "3D Massing Options",
    description:
      "2–3 buildable design candidates generated within your legal envelope, each with unit mix, GFA, and retail breakdown.",
    metric: "Option A: 120 units · 18,500 m²",
    accent: "violet",
    iconPath:
      "M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z",
  },
  {
    step: "03",
    title: "Financial Pro-Forma",
    description:
      "Construction cost estimate, CMHC-calibrated rent projections, debt service, and IRR scenarios at 5 and 10 years.",
    metric: "IRR (5y): 14.2% · Est. cost: $42M",
    accent: "emerald",
    iconPath: "M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6",
  },
  {
    step: "04",
    title: "Council Vote Prediction",
    description:
      "XGBoost classifier trained on 12 years of Toronto council voting records. Identifies swing councillors and approval levers.",
    metric: "73% approval probability · 3 swing votes",
    accent: "amber",
    iconPath: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  {
    step: "05",
    title: "Community Opposition Forecast",
    description:
      "Expected deputation volume, organized groups likely to mobilize, top concerns weighted by historical precedent.",
    metric: "~18 deputations · Low opposition risk",
    accent: "rose",
    iconPath:
      "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75M9 7a4 4 0 100 8 4 4 0 000-8z",
  },
  {
    step: "06",
    title: "Go / No-Go Recommendation",
    description:
      "Principal agent aggregates all signals and delivers a confidence-scored acquisition decision with written rationale.",
    metric: "BUY · 82% confidence",
    accent: "slate",
    iconPath:
      "M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z",
  },
];

// ─── accent colour maps ───────────────────────────────────────────────────────
//
// Blue surface overrides are in globals.css (.dark .bg-blue-50 etc.) so no
// dark: prefix needed for blue.  All other accent colours are not covered by
// globals.css and must carry explicit dark: variants so they read correctly on
// the dark card background (#1e293b from .dark .bg-white).

const accentMap: Record<
  Accent,
  { iconBg: string; iconText: string; metric: string; step: string }
> = {
  blue: {
    iconBg: "bg-blue-50",
    iconText: "text-blue-600",
    metric: "bg-blue-50 text-blue-700 border-blue-100",
    step: "text-blue-500",
  },
  violet: {
    iconBg: "bg-violet-50 dark:bg-violet-950",
    iconText: "text-violet-600 dark:text-violet-400",
    metric:
      "bg-violet-50 dark:bg-violet-950 text-violet-700 dark:text-violet-300 border-violet-100 dark:border-violet-900",
    step: "text-violet-500 dark:text-violet-400",
  },
  emerald: {
    iconBg: "bg-emerald-50 dark:bg-emerald-950",
    iconText: "text-emerald-600 dark:text-emerald-400",
    metric:
      "bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-100 dark:border-emerald-900",
    step: "text-emerald-500 dark:text-emerald-400",
  },
  amber: {
    iconBg: "bg-amber-50 dark:bg-amber-950",
    iconText: "text-amber-600 dark:text-amber-400",
    metric:
      "bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border-amber-100 dark:border-amber-900",
    step: "text-amber-500 dark:text-amber-400",
  },
  rose: {
    iconBg: "bg-rose-50 dark:bg-rose-950",
    iconText: "text-rose-600 dark:text-rose-400",
    metric:
      "bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border-rose-100 dark:border-rose-900",
    step: "text-rose-500 dark:text-rose-400",
  },
  slate: {
    iconBg: "bg-slate-100",
    iconText: "text-slate-600",
    metric: "bg-slate-50 text-slate-700 border-slate-200",
    step: "text-slate-400",
  },
};

// ─── section ──────────────────────────────────────────────────────────────────

export default function FeatureCards() {
  const ref = useRef<HTMLElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section id="features" ref={ref} className="bg-white px-6 py-20">
      <div className="mx-auto max-w-5xl">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 18 }}
          transition={{ duration: 0.5 }}
          className="mb-12 text-center"
        >
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
            What you get
          </p>
          <h2 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            6 decision-ready deliverables
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-base text-slate-500">
            Every AutoSite brief combines Toronto-specific data, trained ML
            models, and AI reasoning into a single, actionable report.
          </p>
        </motion.div>

        {/* Card grid */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => {
            const a = accentMap[f.accent];
            return (
              <motion.article
                key={f.title}
                initial={{ opacity: 0, y: 28 }}
                animate={
                  isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 28 }
                }
                transition={{ duration: 0.45, delay: i * 0.07 }}
                className="flex flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow duration-200 hover:shadow-md"
              >
                {/* Icon + step row */}
                <div className="mb-4 flex items-center gap-3">
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${a.iconBg}`}
                  >
                    <svg
                      viewBox="0 0 24 24"
                      className={`h-5 w-5 ${a.iconText}`}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d={f.iconPath} />
                    </svg>
                  </div>
                  <span className={`text-xs font-bold ${a.step}`}>
                    {f.step}
                  </span>
                </div>

                {/* Title */}
                <h3 className="text-base font-bold leading-snug text-slate-900">
                  {f.title}
                </h3>

                {/* Description */}
                <p className="mt-2 flex-1 text-sm leading-relaxed text-slate-500">
                  {f.description}
                </p>

                {/* Sample metric chip */}
                <div
                  className={`mt-4 inline-block rounded-lg border px-3 py-1.5 font-mono text-xs font-medium ${a.metric}`}
                >
                  {f.metric}
                </div>
              </motion.article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
