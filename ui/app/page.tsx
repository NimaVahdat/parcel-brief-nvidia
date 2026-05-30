"use client";

import dynamic from "next/dynamic";

const ParcelMap = dynamic(() => import("@/components/ParcelMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-slate-100">
      <p className="text-sm text-slate-500">Loading map…</p>
    </div>
  ),
});

const DELIVERABLES = [
  {
    label: "Legal building envelope",
    detail: "Max height, FSI, setbacks, permitted uses",
  },
  {
    label: "3D massing options",
    detail: "Candidate designs that fit the zoning envelope",
  },
  {
    label: "Financial model",
    detail: "Construction cost, IRR over 5 and 10 years, rent projections",
  },
  {
    label: "Council vote prediction",
    detail: "Approval probability, swing councillors, levers",
  },
  {
    label: "Community response",
    detail: "Expected opposition volume and top concerns",
  },
  {
    label: "Go / No-Go recommendation",
    detail: "Confidence score and dominant sensitivities",
  },
];

export default function Home() {
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Top bar */}
      <header className="flex shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded bg-blue-600">
            <span className="text-xs font-bold text-white">AS</span>
          </div>
          <span className="text-base font-semibold tracking-tight text-slate-900">
            AutoSite
          </span>
        </div>
        <div className="h-4 w-px bg-slate-200" />
        <span className="hidden text-sm text-slate-500 sm:block">
          Toronto Site Pre-Acquisition Analysis
        </span>
        <div className="ml-auto">
          <span className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-400">
            NVIDIA Spark Hack · May 2026
          </span>
        </div>
      </header>

      {/* Content: sidebar + map */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar — desktop only */}
        <aside className="hidden w-72 shrink-0 flex-col overflow-y-auto border-r border-slate-200 bg-white lg:flex xl:w-80">
          <div className="space-y-6 p-6">
            {/* Hero */}
            <div>
              <h1 className="text-2xl font-bold leading-tight text-slate-900">
                Development Brief
                <br />
                <span className="text-blue-600">in minutes.</span>
              </h1>
              <p className="mt-3 text-sm leading-relaxed text-slate-600">
                Pick any Toronto parcel and get a decision-grade pre-acquisition
                analysis — building envelope, financial model, council vote
                prediction, and community response forecast.
              </p>
              <p className="mt-2 text-xs text-slate-400">
                Replaces a 4–8 week, $150K–$300K consultant workflow.
              </p>
            </div>

            {/* What you get */}
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                What&apos;s in the brief
              </p>
              <ul className="space-y-3">
                {DELIVERABLES.map(({ label, detail }) => (
                  <li key={label} className="flex gap-3">
                    <div className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
                    <div>
                      <p className="text-sm font-medium text-slate-800">
                        {label}
                      </p>
                      <p className="text-xs text-slate-500">{detail}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* How to use */}
            <div className="rounded-lg border border-blue-100 bg-blue-50 p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-blue-600">
                How to use
              </p>
              <ol className="space-y-2 text-sm text-blue-900">
                <li className="flex gap-2">
                  <span className="font-bold">1.</span>
                  Zoom to any Toronto neighbourhood
                </li>
                <li className="flex gap-2">
                  <span className="font-bold">2.</span>
                  Click a parcel on the map
                </li>
                <li className="flex gap-2">
                  <span className="font-bold">3.</span>
                  Wait ~60 s for your brief
                </li>
              </ol>
            </div>
          </div>
        </aside>

        {/* Map fills the rest */}
        <main className="relative flex-1">
          {/* Mobile instruction chip */}
          <div className="pointer-events-none absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-full border border-slate-200 bg-white/90 px-4 py-2 text-sm text-slate-700 shadow-sm backdrop-blur-sm lg:hidden">
            Click any parcel to generate a Development Brief
          </div>
          <ParcelMap />
        </main>
      </div>
    </div>
  );
}
