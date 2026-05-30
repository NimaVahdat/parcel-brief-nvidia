// Shown by Next.js Suspense only during the brief initial server render.
// The real loading experience is handled client-side by AnalysisView.
export default function Loading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="flex h-8 w-8 items-center justify-center rounded bg-blue-600">
        <span className="text-xs font-bold text-white">AS</span>
      </div>
    </div>
  );
}
