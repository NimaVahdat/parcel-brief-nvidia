import Link from "next/link";

import BriefViewer from "@/components/BriefViewer";
import { analyze } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AnalyzePage({
  params,
}: {
  params: { parcelId: string };
}) {
  const parcelId = decodeURIComponent(params.parcelId);

  let brief;
  let error: string | null = null;
  try {
    brief = await analyze(parcelId);
  } catch (e) {
    error = (e as Error).message;
  }

  return (
    <main className="min-h-screen bg-neutral-50">
      <header className="border-b bg-white px-6 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">Development Brief</h1>
            <p className="text-sm text-neutral-600">Parcel: {parcelId}</p>
          </div>
          <Link href="/" className="text-sm text-blue-600 hover:underline">
            ← back to map
          </Link>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-6 py-6">
        {error && (
          <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            Failed to load brief: {error}
            <br />
            Is the connector running on http://localhost:8000?
          </div>
        )}
        {brief && <BriefViewer brief={brief} />}
      </div>
    </main>
  );
}
