"use client";

import { useRouter } from "next/navigation";
import { MapContainer, TileLayer, useMapEvents } from "react-leaflet";

const TORONTO_CENTER: [number, number] = [43.6532, -79.3832];

function ClickToAnalyze() {
  const router = useRouter();
  useMapEvents({
    click(e) {
      // TODO: replace lat/lng-as-id with a real parcel lookup against
      // site-proforma. For now we encode the click point as the parcel id
      // so the demo flow works end-to-end.
      const parcelId = `${e.latlng.lat.toFixed(5)}_${e.latlng.lng.toFixed(5)}`;
      router.push(`/analyze/${parcelId}`);
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
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickToAnalyze />
    </MapContainer>
  );
}
