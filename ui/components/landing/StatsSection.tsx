"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";

// ─── types ────────────────────────────────────────────────────────────────────

interface Stat {
  prefix?: string;
  target: number;
  suffix: string;
  label: string;
  sublabel: string;
}

// ─── data ─────────────────────────────────────────────────────────────────────

const STATS: Stat[] = [
  {
    target: 8,
    suffix: "",
    label: "AI Agents",
    sublabel: "Running in parallel, orchestrated by LangGraph",
  },
  {
    target: 60,
    suffix: " s",
    label: "Analysis time",
    sublabel: "From parcel click to complete development brief",
  },
  {
    prefix: "$",
    target: 150,
    suffix: "K+",
    label: "Saved per analysis",
    sublabel: "vs. traditional 4–8 week consultant workflow",
  },
  {
    target: 6,
    suffix: "",
    label: "Decision deliverables",
    sublabel:
      "Zoning · Massing · Financials · Vote forecast · Community · Go/No-Go",
  },
];

// ─── animated number ──────────────────────────────────────────────────────────

function CountUpNumber({
  prefix = "",
  target,
  suffix,
  active,
}: {
  prefix?: string;
  target: number;
  suffix: string;
  active: boolean;
}) {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    if (!active) return;
    const duration = 1500;
    let start: number | null = null;

    function step(ts: number) {
      if (!start) start = ts;
      const p = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
      setValue(Math.round(eased * target));
      if (p < 1) rafRef.current = requestAnimationFrame(step);
    }

    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [active, target]);

  return (
    <span className="tabular-nums">
      {prefix}
      {value}
      {suffix}
    </span>
  );
}

// ─── section ─────────────────────────────────────────────────────────────────

export default function StatsSection() {
  const ref = useRef<HTMLElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section ref={ref} className="bg-slate-50 px-6 py-20">
      <div className="mx-auto max-w-5xl">
        <motion.p
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : { opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-14 text-center text-xs font-semibold uppercase tracking-widest text-slate-400"
        >
          By the numbers
        </motion.p>

        <div className="grid grid-cols-2 gap-10 lg:grid-cols-4">
          {STATS.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 24 }}
              animate={
                isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }
              }
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="flex flex-col items-center text-center"
            >
              {/* Large animated number */}
              <div className="text-5xl font-extrabold tracking-tight text-slate-900 sm:text-6xl">
                <CountUpNumber
                  prefix={stat.prefix}
                  target={stat.target}
                  suffix={stat.suffix}
                  active={isInView}
                />
              </div>

              {/* Divider */}
              <div className="my-3 h-px w-8 bg-blue-200" />

              <p className="text-sm font-semibold text-slate-800">
                {stat.label}
              </p>
              <p className="mt-1.5 text-xs leading-snug text-slate-400">
                {stat.sublabel}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
