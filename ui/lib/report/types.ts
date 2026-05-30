import type { ProjectOverrides } from "@/lib/api";

// Canonical identifiers for the six exportable brief sections. The order of the
// union has no meaning — canonical ordering lives in `sections.ts`.
export type SectionId =
  | "executive-summary"
  | "key-metrics"
  | "approval-community"
  | "financial-model"
  | "site"
  | "design-options";

// A user-facing section definition, used to render the export menu.
export interface SectionDef {
  id: SectionId;
  label: string;
}

// The structured, render-target-agnostic content of one report section. The PDF
// renderer walks these blocks; keeping them declarative makes the assembler
// pure and unit-testable without a PDF engine.
export type ReportBlock =
  | { kind: "paragraph"; text: string }
  | { kind: "subheading"; text: string }
  | { kind: "keyValue"; rows: Array<{ label: string; value: string }> }
  | { kind: "bullets"; label?: string; items: string[] }
  | { kind: "table"; columns: string[]; rows: string[][] };

// One assembled report section: a heading plus its ordered content blocks.
export interface ReportSection {
  id: SectionId;
  heading: string;
  blocks: ReportBlock[];
}

// The full assembled report: an ordered list of sections.
export type ReportModel = ReportSection[];

// Cover metadata stamped onto the document header and footer.
export interface ReportMeta {
  parcelId: string;
  generatedAt: Date;
  overrides?: ProjectOverrides;
}
