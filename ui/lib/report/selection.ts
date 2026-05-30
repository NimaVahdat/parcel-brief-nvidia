import type { SectionId } from "./types";
import { SECTION_ORDER } from "./sections";

/**
 * Builds the default selection — every section checked. Export defaults to the
 * full brief; users deselect what they don't want.
 *
 * @returns {Set<SectionId>} A new set containing all section ids.
 */
export function initialSelection(): Set<SectionId> {
  return new Set(SECTION_ORDER);
}

/**
 * Returns a new selection with the given section toggled. Never mutates the
 * input set (immutable update).
 *
 * @param {ReadonlySet<SectionId>} current - The current selection.
 * @param {SectionId} id - The section to add (if absent) or remove (if present).
 * @returns {Set<SectionId>} A new set reflecting the toggle.
 */
export function toggleSection(
  current: ReadonlySet<SectionId>,
  id: SectionId
): Set<SectionId> {
  const next = new Set(current);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  return next;
}

/**
 * Builds a selection containing every section.
 *
 * @returns {Set<SectionId>} A new set with all section ids.
 */
export function selectAll(): Set<SectionId> {
  return new Set(SECTION_ORDER);
}

/**
 * Builds an empty selection.
 *
 * @returns {Set<SectionId>} A new empty set.
 */
export function clearAll(): Set<SectionId> {
  return new Set();
}

/**
 * Reports whether the current selection permits an export (at least one
 * section chosen).
 *
 * @param {ReadonlySet<SectionId>} current - The current selection.
 * @returns {boolean} True when one or more sections are selected.
 */
export function canExport(current: ReadonlySet<SectionId>): boolean {
  return current.size > 0;
}

/**
 * Projects a selection onto canonical document order, dropping unselected ids.
 *
 * @param {ReadonlySet<SectionId>} current - The current selection.
 * @returns {SectionId[]} Selected ids sorted into canonical order.
 */
export function orderedSelection(
  current: ReadonlySet<SectionId>
): SectionId[] {
  return SECTION_ORDER.filter((id) => current.has(id));
}
