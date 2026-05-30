import type { SectionDef, SectionId } from "./types";

// The six exportable sections, in canonical (document) order. This is the
// single source of truth shared by the export menu and the report assembler —
// each entry maps 1:1 to a rendered block in `components/BriefViewer.tsx`.
export const SECTIONS: readonly SectionDef[] = [
  { id: "executive-summary", label: "Executive Summary" },
  { id: "key-metrics", label: "Key Metrics" },
  { id: "approval-community", label: "Approval Forecast & Community Response" },
  { id: "financial-model", label: "Financial Model" },
  { id: "site", label: "Site Fundamentals & Constraints" },
  { id: "design-options", label: "Design Options" },
] as const;

// The canonical order of section ids, derived from `SECTIONS`. Used to sort any
// user selection back into document order.
export const SECTION_ORDER: readonly SectionId[] = SECTIONS.map((s) => s.id);
