import { useCallback, useMemo, useState } from "react";
import type { SectionId } from "@/lib/report/types";
import {
  canExport as pureCanExport,
  clearAll as pureClearAll,
  initialSelection,
  orderedSelection,
  selectAll as pureSelectAll,
  toggleSection,
} from "@/lib/report/selection";

// The reactive selection state exposed to the export menu.
export interface SectionSelection {
  selected: Set<SectionId>;
  orderedIds: SectionId[];
  canExport: boolean;
  isSelected: (id: SectionId) => boolean;
  toggle: (id: SectionId) => void;
  selectAll: () => void;
  clearAll: () => void;
}

/**
 * React hook managing which brief sections are selected for export. State and
 * transitions are delegated to the pure helpers in `lib/report/selection`, so
 * the component layer stays free of selection logic.
 *
 * @returns {SectionSelection} The current selection plus its mutators and derived flags.
 */
export function useSectionSelection(): SectionSelection {
  const [selected, setSelected] = useState<Set<SectionId>>(initialSelection);

  const toggle = useCallback((id: SectionId) => {
    setSelected((current) => toggleSection(current, id));
  }, []);

  const selectAll = useCallback(() => setSelected(pureSelectAll()), []);
  const clearAll = useCallback(() => setSelected(pureClearAll()), []);

  const isSelected = useCallback((id: SectionId) => selected.has(id), [selected]);
  const orderedIds = useMemo(() => orderedSelection(selected), [selected]);

  return {
    selected,
    orderedIds,
    canExport: pureCanExport(selected),
    isSelected,
    toggle,
    selectAll,
    clearAll,
  };
}
