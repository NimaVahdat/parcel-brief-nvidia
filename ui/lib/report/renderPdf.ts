import type { jsPDF, TextOptionsLight } from "jspdf";
import type { ProjectOverrides } from "@/lib/api";
import type { ReportBlock, ReportModel, ReportMeta } from "./types";

// ── layout constants (points; 72pt = 1in, letter = 612 × 792) ─────────────────
const MARGIN = 54;
const FONT = "helvetica";
const COLOR_TEXT: [number, number, number] = [30, 41, 59]; // slate-800
const COLOR_MUTED: [number, number, number] = [100, 116, 139]; // slate-500
const COLOR_ACCENT: [number, number, number] = [37, 99, 235]; // blue-600
const COLOR_RULE: [number, number, number] = [226, 232, 240]; // slate-200
const FOOTER_OFFSET = 28; // pt from the page bottom edge to the footer baseline
const HEADING_MIN_SPACE = 40; // pt of vertical space required before a section heading
const MIN_LABEL_WIDTH = 40; // pt floor for a wrapped key/value label column
const LABEL_VALUE_GAP = 12; // pt gap between a key label and its right-aligned value

// A mutable drawing cursor threaded through the layout helpers. Local and
// short-lived — confined to a single render pass.
interface Cursor {
  doc: jsPDF;
  y: number;
  pageWidth: number;
  pageHeight: number;
  contentWidth: number;
}

/**
 * Converts a point font size to a comfortable line height in points.
 *
 * @param {number} size - The font size in points.
 * @returns {number} The line height in points.
 */
function lineHeight(size: number): number {
  return size * 1.32;
}

/**
 * Adds a new page and resets the cursor to the top content margin.
 *
 * @param {Cursor} c - The drawing cursor (mutated in place).
 * @returns {void}
 */
function newPage(c: Cursor): void {
  c.doc.addPage();
  c.y = MARGIN;
}

/**
 * Ensures at least `needed` points of vertical space remain, starting a new
 * page when the content would overflow the bottom margin.
 *
 * @param {Cursor} c - The drawing cursor (mutated in place).
 * @param {number} needed - The vertical space required, in points.
 * @returns {void}
 */
function ensureSpace(c: Cursor, needed: number): void {
  if (c.y + needed > c.pageHeight - MARGIN) newPage(c);
}

/**
 * Draws one or more wrapped lines of text and advances the cursor.
 *
 * @param {Cursor} c - The drawing cursor (mutated in place).
 * @param {string} text - The text to render (wrapped to the content width).
 * @param {object} opts - Rendering options.
 * @param {number} opts.size - Font size in points.
 * @param {"normal"|"bold"} opts.style - Font weight.
 * @param {[number,number,number]} opts.color - RGB text colour.
 * @param {number} [opts.indent=0] - Left indent in points.
 * @param {number} [opts.gapAfter=0] - Extra space after the block in points.
 * @returns {void}
 */
function drawText(
  c: Cursor,
  text: string,
  opts: {
    size: number;
    style: "normal" | "bold";
    color: [number, number, number];
    indent?: number;
    gapAfter?: number;
  }
): void {
  const indent = opts.indent ?? 0;
  c.doc.setFont(FONT, opts.style);
  c.doc.setFontSize(opts.size);
  c.doc.setTextColor(...opts.color);
  const lines: string[] = c.doc.splitTextToSize(text, c.contentWidth - indent);
  const lh = lineHeight(opts.size);
  for (const line of lines) {
    ensureSpace(c, lh);
    c.doc.text(line, MARGIN + indent, c.y);
    c.y += lh;
  }
  c.y += opts.gapAfter ?? 0;
}

/**
 * Draws a right-aligned label/value row (label left, value right). Wraps the
 * label if it is long; keeps the value on the baseline of the first line.
 *
 * @param {Cursor} c - The drawing cursor (mutated in place).
 * @param {string} label - The left-hand label.
 * @param {string} value - The right-hand value.
 * @returns {void}
 */
function drawKeyValueRow(c: Cursor, label: string, value: string): void {
  const size = 10;
  const lh = lineHeight(size);
  c.doc.setFontSize(size);
  c.doc.setFont(FONT, "normal");
  const valueWidth = c.doc.getTextWidth(value);
  // Floor the label column so an unusually wide value can never produce a
  // negative wrap width (which `splitTextToSize` mishandles).
  const labelWidth = Math.max(MIN_LABEL_WIDTH, c.contentWidth - valueWidth - LABEL_VALUE_GAP);
  const labelLines: string[] = c.doc.splitTextToSize(label, labelWidth);
  ensureSpace(c, lh * labelLines.length);
  c.doc.setTextColor(...COLOR_MUTED);
  c.doc.text(labelLines, MARGIN, c.y);
  c.doc.setTextColor(...COLOR_TEXT);
  c.doc.setFont(FONT, "bold");
  c.doc.text(value, c.pageWidth - MARGIN, c.y, { align: "right" } as TextOptionsLight);
  c.y += lh * labelLines.length;
}

/**
 * Draws a simple grid table (header row + body rows) with evenly spaced
 * columns and a hairline under the header.
 *
 * @param {Cursor} c - The drawing cursor (mutated in place).
 * @param {string[]} columns - Column headers.
 * @param {string[][]} rows - Row cells, aligned to `columns`.
 * @returns {void}
 */
function drawTable(c: Cursor, columns: string[], rows: string[][]): void {
  const size = 9;
  const lh = lineHeight(size);
  const colWidth = c.contentWidth / columns.length;
  const drawRow = (cells: string[], bold: boolean) => {
    ensureSpace(c, lh);
    c.doc.setFont(FONT, bold ? "bold" : "normal");
    c.doc.setFontSize(size);
    c.doc.setTextColor(...(bold ? COLOR_TEXT : COLOR_MUTED));
    cells.forEach((cell, i) => {
      const align = i === 0 ? "left" : "right";
      const x = i === 0 ? MARGIN : MARGIN + colWidth * (i + 1) - 4;
      c.doc.text(String(cell), x, c.y, { align } as TextOptionsLight);
    });
    c.y += lh;
  };
  drawRow(columns, true);
  c.doc.setDrawColor(...COLOR_RULE);
  c.doc.setLineWidth(0.5);
  c.doc.line(MARGIN, c.y - lh + 3, c.pageWidth - MARGIN, c.y - lh + 3);
  rows.forEach((r) => drawRow(r, false));
}

/**
 * Renders a single content block at the current cursor position.
 *
 * @param {Cursor} c - The drawing cursor (mutated in place).
 * @param {ReportBlock} block - The block to render.
 * @returns {void}
 */
function drawBlock(c: Cursor, block: ReportBlock): void {
  switch (block.kind) {
    case "subheading":
      ensureSpace(c, lineHeight(11) + 4);
      drawText(c, block.text, { size: 11, style: "bold", color: COLOR_TEXT, gapAfter: 2 });
      break;
    case "paragraph":
      drawText(c, block.text, { size: 10, style: "normal", color: COLOR_TEXT, gapAfter: 6 });
      break;
    case "keyValue":
      block.rows.forEach((row) => drawKeyValueRow(c, row.label, row.value));
      c.y += 6;
      break;
    case "bullets":
      if (block.label) {
        drawText(c, block.label, { size: 9, style: "bold", color: COLOR_MUTED, gapAfter: 1 });
      }
      block.items.forEach((item) =>
        drawText(c, `•  ${item}`, { size: 10, style: "normal", color: COLOR_TEXT, indent: 6 })
      );
      c.y += 6;
      break;
    case "table":
      drawTable(c, block.columns, block.rows);
      c.y += 6;
      break;
  }
}

/**
 * Formats a Date as a long, locale-neutral document date (e.g. "30 May 2026").
 *
 * @param {Date} d - The date to format.
 * @returns {string} The formatted date string.
 */
function formatDate(d: Date): string {
  return d.toLocaleDateString("en-CA", { day: "numeric", month: "long", year: "numeric" });
}

/**
 * Builds a one-line summary of any applied project overrides, or null when the
 * brief reflects the auto-generated massing.
 *
 * @param {ProjectOverrides|undefined} overrides - The applied overrides, if any.
 * @returns {string|null} A summary line, or null when no overrides are applied.
 */
function overridesLine(overrides: ProjectOverrides | undefined): string | null {
  if (!overrides) return null;
  const parts: string[] = [];
  if (overrides.height_m != null) parts.push(`${overrides.height_m} m`);
  if (overrides.total_units != null) parts.push(`${overrides.total_units} units`);
  if (overrides.affordable_units != null) parts.push(`${overrides.affordable_units} affordable`);
  if (overrides.retail_sqft != null) parts.push(`${overrides.retail_sqft} sqft retail`);
  return parts.length > 0 ? `Custom scenario — ${parts.join(" · ")}` : null;
}

/**
 * Draws the document title block (title, parcel id, date, optional scenario).
 *
 * @param {Cursor} c - The drawing cursor (mutated in place).
 * @param {ReportMeta} meta - The report metadata.
 * @returns {void}
 */
function drawTitle(c: Cursor, meta: ReportMeta): void {
  drawText(c, "Development Brief", { size: 22, style: "bold", color: COLOR_TEXT, gapAfter: 4 });
  drawText(c, `Parcel ${meta.parcelId}`, { size: 12, style: "normal", color: COLOR_ACCENT });
  drawText(c, `Generated ${formatDate(meta.generatedAt)}`, {
    size: 10,
    style: "normal",
    color: COLOR_MUTED,
  });
  const scenario = overridesLine(meta.overrides);
  if (scenario) {
    drawText(c, scenario, { size: 10, style: "normal", color: COLOR_MUTED });
  }
  c.y += 6;
  c.doc.setDrawColor(...COLOR_RULE);
  c.doc.setLineWidth(1);
  c.doc.line(MARGIN, c.y, c.pageWidth - MARGIN, c.y);
  c.y += 18;
}

/**
 * Draws a section heading with an accent rule above it.
 *
 * @param {Cursor} c - The drawing cursor (mutated in place).
 * @param {string} heading - The section heading text.
 * @returns {void}
 */
function drawSectionHeading(c: Cursor, heading: string): void {
  ensureSpace(c, HEADING_MIN_SPACE);
  c.y += 4;
  drawText(c, heading, { size: 14, style: "bold", color: COLOR_ACCENT, gapAfter: 6 });
}

/**
 * Stamps a "Page i of N" footer plus the parcel id on every page. Must run
 * after all content is laid out, since the total page count is known only then.
 *
 * @param {jsPDF} doc - The completed document.
 * @param {string} parcelId - The parcel id shown in the footer.
 * @returns {void}
 */
function stampFooters(doc: jsPDF, parcelId: string): void {
  const total = doc.getNumberOfPages();
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  for (let i = 1; i <= total; i++) {
    doc.setPage(i);
    doc.setFont(FONT, "normal");
    doc.setFontSize(8);
    doc.setTextColor(...COLOR_MUTED);
    doc.text(`AutoSite · Parcel ${parcelId}`, MARGIN, pageHeight - FOOTER_OFFSET);
    doc.text(`Page ${i} of ${total}`, pageWidth - MARGIN, pageHeight - FOOTER_OFFSET, {
      align: "right",
    } as TextOptionsLight);
  }
}

/**
 * Slugifies a parcel id for use in a download filename.
 *
 * @param {string} parcelId - The raw parcel id.
 * @returns {string} A filesystem-safe slug (falls back to "brief" when empty).
 */
function slugify(parcelId: string): string {
  const slug = parcelId.replace(/[^a-z0-9]+/gi, "-").replace(/^-+|-+$/g, "").toLowerCase();
  return slug || "brief";
}

/**
 * Triggers a browser download of the document with a guaranteed filename and
 * MIME type. Building the Blob explicitly (rather than relying on jsPDF's
 * bundled `save()`) ensures the ".pdf" extension and "application/pdf" type
 * survive across browsers — Safari/WebKit ignore the `download` filename on a
 * detached anchor, so the link is appended to the document before clicking.
 * Exported for unit testing.
 *
 * @param {jsPDF} doc - The completed document.
 * @param {string} filename - The download filename, including the .pdf extension.
 * @returns {void}
 */
export function triggerDownload(doc: jsPDF, filename: string): void {
  const blob = new Blob([doc.output("arraybuffer")], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

/**
 * Renders the assembled report model to a PDF and triggers a browser download.
 * jsPDF is dynamically imported here so it is code-split out of the initial
 * route bundle and only loaded when the user actually exports.
 *
 * @param {ReportModel} model - The ordered sections to render.
 * @param {ReportMeta} meta - Document metadata (parcel id, date, overrides).
 * @returns {Promise<void>} Resolves once the download has been triggered.
 * @throws {Error} Propagates any failure from jsPDF construction or saving.
 */
export async function renderReportToPdf(model: ReportModel, meta: ReportMeta): Promise<void> {
  const { jsPDF: JsPDF } = await import("jspdf");
  const doc = new JsPDF({ unit: "pt", format: "letter" });

  const c: Cursor = {
    doc,
    y: MARGIN,
    pageWidth: doc.internal.pageSize.getWidth(),
    pageHeight: doc.internal.pageSize.getHeight(),
    contentWidth: doc.internal.pageSize.getWidth() - MARGIN * 2,
  };

  drawTitle(c, meta);
  model.forEach((section) => {
    drawSectionHeading(c, section.heading);
    section.blocks.forEach((block) => drawBlock(c, block));
    c.y += 10;
  });

  stampFooters(doc, meta.parcelId);
  triggerDownload(doc, `development-brief-${slugify(meta.parcelId)}.pdf`);
}
