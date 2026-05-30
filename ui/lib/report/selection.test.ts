import { describe, it, expect } from "vitest";
import {
  initialSelection,
  toggleSection,
  selectAll,
  clearAll,
  canExport,
  orderedSelection,
} from "./selection";
import { SECTION_ORDER } from "./sections";

describe("section selection state", () => {
  it("starts with every section selected", () => {
    const sel = initialSelection();
    expect(sel.size).toBe(SECTION_ORDER.length);
    for (const id of SECTION_ORDER) {
      expect(sel.has(id)).toBe(true);
    }
  });

  it("toggleSection removes a selected id without mutating the input", () => {
    const sel = initialSelection();
    const next = toggleSection(sel, "financial-model");

    expect(next.has("financial-model")).toBe(false);
    // original is untouched (immutability)
    expect(sel.has("financial-model")).toBe(true);
    expect(next.size).toBe(sel.size - 1);
  });

  it("toggleSection re-adds a deselected id", () => {
    const sel = toggleSection(initialSelection(), "site");
    const next = toggleSection(sel, "site");
    expect(next.has("site")).toBe(true);
  });

  it("clearAll empties the selection and disables export", () => {
    const sel = clearAll();
    expect(sel.size).toBe(0);
    expect(canExport(sel)).toBe(false);
  });

  it("selectAll restores every section", () => {
    const sel = selectAll();
    expect(sel.size).toBe(SECTION_ORDER.length);
    expect(canExport(sel)).toBe(true);
  });

  it("canExport is true when at least one section is selected", () => {
    expect(canExport(new Set(["site"]))).toBe(true);
    expect(canExport(new Set())).toBe(false);
  });

  it("orderedSelection returns ids in canonical order regardless of insertion order", () => {
    const sel = new Set<typeof SECTION_ORDER[number]>([
      "design-options",
      "executive-summary",
      "financial-model",
    ]);
    expect(orderedSelection(sel)).toEqual([
      "executive-summary",
      "financial-model",
      "design-options",
    ]);
  });
});
