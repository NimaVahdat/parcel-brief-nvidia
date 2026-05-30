// Formatting helpers for the PDF report. These intentionally mirror the private
// helpers in `components/BriefViewer.tsx` so the exported document reads the same
// as the on-screen brief, without importing from a component module.

/**
 * Formats a number as a compact currency string (e.g. 18_500_000 → "$18.5M").
 *
 * @param {number} n - The raw dollar amount.
 * @returns {string} A compact, human-readable currency string.
 */
export function fmtMoney(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

/**
 * Formats a 0–1 ratio as a percentage string (e.g. 0.142 → "14%" or "14.2%").
 *
 * @param {number} n - The ratio to format, where 1 represents 100%.
 * @param {number} [decimals=0] - Number of decimal places to render.
 * @returns {string} The percentage string including the "%" suffix.
 */
export function fmtPct(n: number, decimals = 0): string {
  return `${(n * 100).toFixed(decimals)}%`;
}

/**
 * Maps an expected deputation count to a qualitative opposition label, matching
 * the thresholds used in the on-screen Community Response card.
 *
 * @param {number} count - The expected number of deputation letters.
 * @returns {string} One of "Low", "Moderate", or "High".
 */
export function oppositionLabel(count: number): string {
  if (count < 20) return "Low";
  if (count < 60) return "Moderate";
  return "High";
}

/**
 * Renders a sensitivity cell value the same way the on-screen table does:
 * ratios (|v| < 1) become percentages, larger magnitudes become currency.
 *
 * @param {number} v - The raw sensitivity value.
 * @returns {string} A percentage or currency string.
 */
export function fmtSensitivity(v: number): string {
  return v < 1 && v > -1 ? fmtPct(v, 1) : fmtMoney(v);
}
