"use client";

import dynamic from "next/dynamic";

// react-leaflet uses the browser's window object; disable SSR.
const ParcelMap = dynamic(() => import("@/components/ParcelMap"), {
  ssr: false,
  loading: () => <div className="p-4">Loading map…</div>,
});

export default function Home() {
  return (
    <main className="flex h-screen flex-col">
      <header className="border-b bg-white px-6 py-3">
        <h1 className="text-xl font-semibold">parcel-brief</h1>
        <p className="text-sm text-neutral-600">
          Click any Toronto parcel to generate a Development Brief.
        </p>
      </header>
      <div className="flex-1">
        <ParcelMap />
      </div>
    </main>
  );
}
