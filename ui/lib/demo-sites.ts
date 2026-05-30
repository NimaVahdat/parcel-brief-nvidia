export const DEMO_SITES = [
  { address: "720 King St W, Toronto",      lat: 43.64413, lng: -79.40280 },
  { address: "2300 Yonge St, Toronto",       lat: 43.70623, lng: -79.39844 },
  { address: "900 Bloor St W, Toronto",      lat: 43.66140, lng: -79.42623 },
  { address: "793 Danforth Ave, Toronto",    lat: 43.67781, lng: -79.34990 },
  { address: "10 Liberty St, Toronto",       lat: 43.63780, lng: -79.41840 },
  { address: "4789 Yonge St, North York",    lat: 43.76480, lng: -79.41430 },
  { address: "5415 Dundas St W, Etobicoke",  lat: 43.64520, lng: -79.54280 },
  { address: "1 Queens Quay W, Toronto",     lat: 43.64160, lng: -79.38050 },
  { address: "300 Borough Dr, Scarborough",  lat: 43.77640, lng: -79.25710 },
  { address: "3080 Dundas St W, Toronto",    lat: 43.66250, lng: -79.46940 },
] as const;

export type DemoSite = (typeof DEMO_SITES)[number];

export function toParcelId(lat: number, lng: number): string {
  return `${lat.toFixed(5)}_${lng.toFixed(5)}`;
}
