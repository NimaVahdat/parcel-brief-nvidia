import Link from "next/link";
import AnalysisView from "@/components/AnalysisView";
import ThemeToggle from "@/components/ThemeToggle";
import type { ProjectOverrides } from "@/lib/api";

export const dynamic = "force-dynamic";

export default function AnalyzePage({
  params,
  searchParams,
}: {
  params: { parcelId: string };
  searchParams?: Record<string, string | string[]>;
}) {
  const parcelId = decodeURIComponent(params.parcelId);

  // Read scenario overrides passed from the homepage scenario panel via URL params.
  // All fields are optional; omitted or invalid values are simply ignored.
  const initialOverrides: ProjectOverrides = {};
  const h = Number(searchParams?.height_m);
  const u = Number(searchParams?.total_units);
  const a = Number(searchParams?.affordable_units);
  if (Number.isFinite(h) && h > 0) initialOverrides.height_m = h;
  if (Number.isFinite(u) && u > 0) initialOverrides.total_units = u;
  if (Number.isFinite(a) && a >= 0) initialOverrides.affordable_units = a;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header — server-rendered, appears instantly */}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded bg-blue-600">
                <span className="text-xs font-bold text-white">AS</span>
              </div>
              <span className="text-base font-semibold tracking-tight text-slate-900">
                AutoSite
              </span>
            </Link>
            <div className="h-4 w-px bg-slate-200" />
            <div>
              <span className="text-sm text-slate-500">Brief for </span>
              <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-sm text-slate-700">
                {parcelId}
              </code>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-sm text-slate-500 transition-colors hover:text-slate-900"
            >
              ← New analysis
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Client-driven analysis: shows staged progress then the brief */}
      <div className="mx-auto max-w-5xl px-6 py-8">
        <AnalysisView parcelId={parcelId} initialOverrides={initialOverrides} />
      </div>
    </div>
  );
}
