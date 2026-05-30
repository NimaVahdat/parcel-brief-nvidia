import Link from "next/link";
import AnalysisView from "@/components/AnalysisView";
import ThemeToggle from "@/components/ThemeToggle";

export const dynamic = "force-dynamic";

export default function AnalyzePage({
  params,
}: {
  params: { parcelId: string };
}) {
  const parcelId = decodeURIComponent(params.parcelId);

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
        <AnalysisView parcelId={parcelId} />
      </div>
    </div>
  );
}
