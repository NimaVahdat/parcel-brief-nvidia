"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  useMapEvents,
} from "react-leaflet";

const TORONTO_CENTER: [number, number] = [43.6532, -79.3832];

interface ClickPoint {
  lat: number;
  lng: number;
}

function ClickToAnalyze({
  onPendingClick,
}: {
  onPendingClick: (pt: ClickPoint) => void;
}) {
  const router = useRouter();
  useMapEvents({
    click(e) {
      const { lat, lng } = e.latlng;
      onPendingClick({ lat, lng });
      const parcelId = `${lat.toFixed(5)}_${lng.toFixed(5)}`;
      setTimeout(() => {
        router.push(`/analyze/${encodeURIComponent(parcelId)}`);
      }, 380);
    },
  });
  return null;
}

export default function ParcelMap() {
  const [clickPt, setClickPt] = useState<ClickPoint | null>(null);

  return (
    <MapContainer
      center={TORONTO_CENTER}
      zoom={13}
      style={{ height: "100%", width: "100%" }}
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickToAnalyze onPendingClick={setClickPt} />
      {clickPt && (
        <CircleMarker
          center={[clickPt.lat, clickPt.lng]}
          radius={10}
          pathOptions={{
            color: "#3b82f6",
            fillColor: "#3b82f6",
            fillOpacity: 0.25,
            weight: 2.5,
          }}
        />
      )}
    </MapContainer>
  );
}
