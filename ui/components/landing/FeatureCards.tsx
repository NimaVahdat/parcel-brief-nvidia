"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";

// ─── data ─────────────────────────────────────────────────────────────────────

type Accent = "blue" | "violet" | "emerald" | "amber" | "rose" | "slate";

interface Feature {
  step: string;
  title: string;
  description: string;
  accent: Accent;
  iconPath: string;
}

const FEATURES: Feature[] = [
  {
    step: "01",
    title: "Zoning & Site Constraints",
    description: "Instantly see what you're allowed to build — height, density, setbacks, and any restrictions on the site.",
    accent: "blue",
    iconPath:
      "M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 10v11M12 10v11M16 10v11",
  },
  {
    step: "02",
    title: "3D Massing Options",
    description: "Get 2–3 buildable design options that fit within the site's legal limits, with unit counts and floor areas.",
    accent: "violet",
    iconPath:
      "M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z",
  },
  {
    step: "03",
    title: "Financial Model",
    description: "Find out if the project makes money — construction cost, projected rents, and investment returns.",
    accent: "emerald",
    iconPath: "M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6",
  },
  {
    step: "04",
    title: "Council Approval Forecast",
    description: "Know your approval odds before filing — and what changes would improve them.",
    accent: "amber",
    iconPath: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  {
    step: "05",
    title: "Community Response",
    description: "See how much public opposition to expect and what concerns the neighbourhood is likely to raise.",
    accent: "rose",
    iconPath:
      "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75M9 7a4 4 0 100 8 4 4 0 000-8z",
  },
  {
    step: "06",
    title: "Go / No-Go Recommendation",
    description: "A clear buy, conditional, or pass verdict — with the key reasons behind it.",
    accent: "slate",
    iconPath:
      "M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z",
  },
];

// ─── accent colour maps ───────────────────────────────────────────────────────
//
// Blue surfaces are overridden by globals.css in dark mode (.dark .bg-blue-50).
// All other accent colours need explicit dark: variants because globals.css does
// not cover them.

const accentMap: Record<Accent, { iconBg: string; iconText: string; step: string }> = {
  blue:    { iconBg: "bg-blue-50",                    iconText: "text-blue-600",                    step: "text-blue-500" },
  violet:  { iconBg: "bg-violet-50 dark:bg-violet-950", iconText: "text-violet-600 dark:text-violet-400", step: "text-violet-500 dark:text-violet-400" },
  emerald: { iconBg: "bg-emerald-50 dark:bg-emerald-950", iconText: "text-emerald-600 dark:text-emerald-400", step: "text-emerald-500 dark:text-emerald-400" },
  amber:   { iconBg: "bg-amber-50 dark:bg-amber-950",  iconText: "text-amber-600 dark:text-amber-400",  step: "text-amber-500 dark:text-amber-400" },
  rose:    { iconBg: "bg-rose-50 dark:bg-rose-950",    iconText: "text-rose-600 dark:text-rose-400",    step: "text-rose-500 dark:text-rose-400" },
  slate:   { iconBg: "bg-slate-100",                   iconText: "text-slate-600",                   step: "text-slate-400" },
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
          <p className="mx-auto mt-4 max-w-lg text-base leading-relaxed text-slate-500">
            Everything a developer needs to decide whether a Toronto site is
            worth pursuing — in 60 seconds.
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
                whileHover={{ y: -3 }}
                className="feature-card-glow flex flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm cursor-default"
              >
                {/* Icon + step */}
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
                <h3 className="text-[15px] font-bold leading-snug text-slate-900">
                  {f.title}
                </h3>

                {/* Description */}
                <p className="mt-2 text-sm leading-relaxed text-slate-500">
                  {f.description}
                </p>
              </motion.article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
