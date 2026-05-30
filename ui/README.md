# ui

## What this does

Next.js 14 front end for parcel-brief. Two pages:

- `/` — Toronto map (react-leaflet). Click anywhere to start an analysis.
- `/analyze/[parcelId]` — Development Brief viewer rendering all six sections returned by the connector.

The UI owns no data and trains no models. It is a thin client over the connector's `/analyze` endpoint.

## How to run

```bash
cd ui
npm install
npm run dev
# → http://localhost:3000
```

Requires the connector running on `:8000` (or override with `NEXT_PUBLIC_CONNECTOR_URL`).

## Current state

- [x] Map renders, click navigates to /analyze/[parcelId]
- [x] Brief viewer renders all six sections from the connector response
- [x] TypeScript types mirror the Pydantic `BriefResponse`
- [ ] Toronto parcel GeoJSON overlay (currently using lat/lng as parcel id placeholder — see ParcelMap.tsx)
- [ ] 3D massing viewer (use three.js or `<model-viewer>` on `brief.design_options.options[i].three_d_uri`)
- [ ] Adjustable project parameters (re-run with edited unit count, affordable share, retail)
- [ ] Export-to-PDF
- [ ] Demo polish (loading states, animated transitions, brand)

## Next tasks

1. Replace the lat/lng-as-parcel-id placeholder in `ParcelMap.tsx` with real parcel polygons from the Toronto Open Data parcels layer. Highlight the clicked parcel.
2. Wire up a 3D viewer in `BriefViewer.tsx` for `design_options.options[i].three_d_uri`. Try `<model-viewer>` first — easiest path for .glb files.
3. Add a parameters panel beside the brief so users can tweak project inputs and re-run.
4. Style pass for demo day. Smooth loading, error states, no jank.

## File map

| File | Purpose |
|---|---|
| `app/layout.tsx` | Root layout + Tailwind + Leaflet CSS |
| `app/globals.css` | Tailwind directives + leaflet.css |
| `app/page.tsx` | Map page (entry) |
| `app/analyze/[parcelId]/page.tsx` | Brief viewer page |
| `components/ParcelMap.tsx` | react-leaflet map (client component) |
| `components/BriefViewer.tsx` | Six-section brief renderer |
| `lib/api.ts` | Connector client + TypeScript types mirroring Pydantic |
