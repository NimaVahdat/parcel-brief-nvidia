"use client";

import { useRouter } from "next/navigation";
import { MapContainer, TileLayer, useMapEvents } from "react-leaflet";

const TORONTO_CENTER: [number, number] = [43.6532, -79.3832];

function ClickToAnalyze() {
  const router = useRouter();
  useMapEvents({
    click(e) {
      // Encodes the click point as the parcel id for the demo flow.
      // TODO: replace with a real parcel lookup against site-proforma.
      const parcelId = `${e.latlng.lat.toFixed(5)}_${e.latlng.lng.toFixed(5)}`;
      router.push(`/analyze/${encodeURIComponent(parcelId)}`);
    },
  });
  return null;
}

export default function ParcelMap() {
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
      <ClickToAnalyze />
    </MapContainer>
  );
}
