"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";

const SOURCES = [
  { label: "Toronto Open Data",  detail: "Zoning · Parcels · Heritage" },
  { label: "CMHC",              detail: "Rents · Market comparables" },
  { label: "TMMIS",             detail: "Council voting records" },
  { label: "NVIDIA Spark",      detail: "GB10 · Inference" },
  { label: "LangGraph",         detail: "Agent orchestration" },
];

export default function TrustBar() {
  const ref = useRef<HTMLElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-40px" });

  return (
    <section
      ref={ref}
      className="border-y border-slate-200 bg-white px-6 py-7"
    >
      <motion.div
        initial={{ opacity: 0 }}
        animate={isInView ? { opacity: 1 } : { opacity: 0 }}
        transition={{ duration: 0.5 }}
        className="mx-auto flex max-w-5xl flex-col items-center gap-5 sm:flex-row sm:gap-8"
      >
        <p className="shrink-0 text-xs font-semibold uppercase tracking-widest text-slate-400">
          Powered by
        </p>

        <div className="flex flex-1 flex-wrap items-center justify-center gap-x-10 gap-y-4 sm:justify-between">
          {SOURCES.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 8 }}
              animate={
                isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }
              }
              transition={{ duration: 0.4, delay: 0.05 + i * 0.07 }}
              className="text-center"
            >
              <p className="text-sm font-bold text-slate-700">{s.label}</p>
              <p className="mt-0.5 text-xs text-slate-400">{s.detail}</p>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </section>
  );
}
