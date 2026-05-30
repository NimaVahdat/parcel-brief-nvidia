"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { BriefResponse, ProjectOverrides } from "@/lib/api";
import { useSectionSelection } from "@/hooks/useSectionSelection";
import { SECTIONS } from "@/lib/report/sections";
import { buildReportModel } from "@/lib/report/buildReportModel";
import { renderReportToPdf } from "@/lib/report/renderPdf";

interface SectionExportMenuProps {
  brief: BriefResponse;
  parcelId: string;
  overrides: ProjectOverrides;
}

/**
 * Extracts a human-readable message from an unknown thrown value.
 *
 * @param {unknown} error - The caught error value.
 * @returns {string} A safe, user-facing error message.
 */
function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Could not generate the report.";
}

// ── checkbox visual ───────────────────────────────────────────────────────────

/**
 * Renders the decorative checkbox box (checked/unchecked). Purely visual — the
 * checked state is conveyed to assistive tech via the parent's `aria-checked`.
 *
 * @param {object} props - Component props.
 * @param {boolean} props.checked - Whether to render the checked state.
 * @returns {JSX.Element} The checkbox glyph.
 */
function CheckboxBox({ checked }: { checked: boolean }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors ${
        checked ? "border-blue-600 bg-blue-600" : "border-slate-300 bg-white"
      }`}
    >
      {checked && (
        <svg viewBox="0 0 10 10" className="h-2.5 w-2.5">
          <polyline
            points="2,5 4,7.5 8,2.5"
            fill="none"
            stroke="white"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </span>
  );
}

// ── main component ────────────────────────────────────────────────────────────

/**
 * Export-report control: a trigger button that opens an accessible popup menu
 * (APG menu + menuitemcheckbox) for choosing which brief sections to include,
 * then generates and downloads a print-document PDF of the current brief.
 *
 * @param {SectionExportMenuProps} props - Component props.
 * @param {BriefResponse} props.brief - The brief currently shown (overrides already applied).
 * @param {string} props.parcelId - The parcel id, stamped onto the report.
 * @param {ProjectOverrides} props.overrides - Applied scenario overrides ({} when auto).
 * @returns {JSX.Element} The export trigger and its popup menu.
 */
export default function SectionExportMenu({
  brief,
  parcelId,
  overrides,
}: SectionExportMenuProps): JSX.Element {
  const { selected, isSelected, toggle, canExport } = useSectionSelection();

  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const menuId = useId();
  const hintId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemsRef = useRef<Array<HTMLButtonElement | null>>([]);

  const exportIndex = SECTIONS.length; // export item sits after the checkboxes
  const lastIndex = exportIndex;
  const hasOverrides = Object.keys(overrides).length > 0;

  // Move focus to the active item whenever the menu opens or the active item changes.
  useEffect(() => {
    if (open) itemsRef.current[activeIndex]?.focus();
  }, [open, activeIndex]);

  // Close on outside pointer interaction (without stealing focus back).
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  /**
   * Closes the menu and returns focus to the trigger (keyboard-dismiss path).
   *
   * @returns {void}
   */
  function closeAndRefocus(): void {
    setOpen(false);
    triggerRef.current?.focus();
  }

  /**
   * Toggles the menu open/closed, resetting the active item when opening.
   *
   * @returns {void}
   */
  function toggleOpen(): void {
    if (open) {
      setOpen(false);
    } else {
      setActiveIndex(0);
      setError(null);
      setOpen(true);
    }
  }

  /**
   * Handles roving-focus and dismissal keys for the menu container.
   *
   * @param {React.KeyboardEvent} event - The keyboard event.
   * @returns {void}
   */
  function onMenuKeyDown(event: React.KeyboardEvent): void {
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, lastIndex));
        break;
      case "ArrowUp":
        event.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        break;
      case "Home":
        event.preventDefault();
        setActiveIndex(0);
        break;
      case "End":
        event.preventDefault();
        setActiveIndex(lastIndex);
        break;
      case "Escape":
        event.preventDefault();
        closeAndRefocus();
        break;
    }
  }

  /**
   * Closes the menu when focus moves outside the control entirely (e.g. Tab or
   * Shift+Tab past the menu). Roving tabindex makes the inactive items
   * non-tabbable, so Tab naturally leaves the menu rather than being trapped.
   *
   * @param {React.FocusEvent} event - The blur (focusout) event from the menu.
   * @returns {void}
   */
  function onMenuFocusOut(event: React.FocusEvent): void {
    const next = event.relatedTarget as Node | null;
    if (!next || (rootRef.current && !rootRef.current.contains(next))) {
      setOpen(false);
    }
  }

  /**
   * Builds the report from the current selection and triggers a PDF download.
   * No-ops when nothing is selected or an export is already running.
   *
   * @returns {Promise<void>} Resolves after the download is triggered or an error is captured.
   */
  async function handleExport(): Promise<void> {
    if (!canExport || exporting) return;
    setError(null);
    setExporting(true);
    try {
      const model = buildReportModel(brief, selected);
      await renderReportToPdf(model, {
        parcelId,
        generatedAt: new Date(),
        overrides: hasOverrides ? overrides : undefined,
      });
      setExporting(false);
      closeAndRefocus();
    } catch (err: unknown) {
      setExporting(false);
      setError(getErrorMessage(err));
    }
  }

  return (
    <div ref={rootRef} className="relative inline-block text-left">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={toggleOpen}
        className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-300"
      >
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
          <path d="M10 2.5a.75.75 0 0 1 .75.75v7.69l2.22-2.22a.75.75 0 1 1 1.06 1.06l-3.5 3.5a.75.75 0 0 1-1.06 0l-3.5-3.5a.75.75 0 1 1 1.06-1.06l2.22 2.22V3.25A.75.75 0 0 1 10 2.5Z" />
          <path d="M3.5 13a.75.75 0 0 1 .75.75v1.5c0 .14.11.25.25.25h11a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 15.5 17h-11A1.75 1.75 0 0 1 2.75 15.25v-1.5A.75.75 0 0 1 3.5 13Z" />
        </svg>
        Export Report
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5 text-slate-400" aria-hidden="true">
          <path
            fillRule="evenodd"
            d="M5.22 7.22a.75.75 0 0 1 1.06 0L10 10.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 8.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {open && (
        <div className="animate-menu-pop absolute right-0 top-full z-20 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
          <p className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Sections to include
          </p>

          <div
            id={menuId}
            role="menu"
            aria-label="Choose report sections to include"
            onKeyDown={onMenuKeyDown}
            onBlur={onMenuFocusOut}
          >
            {SECTIONS.map((section, idx) => {
              const checked = isSelected(section.id);
              return (
                <button
                  key={section.id}
                  ref={(el) => {
                    itemsRef.current[idx] = el;
                  }}
                  type="button"
                  role="menuitemcheckbox"
                  aria-checked={checked}
                  tabIndex={activeIndex === idx ? 0 : -1}
                  onClick={() => toggle(section.id)}
                  className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
                >
                  <CheckboxBox checked={checked} />
                  {section.label}
                </button>
              );
            })}

            <div className="my-1.5 h-px bg-slate-100" role="separator" />

            <button
              ref={(el) => {
                itemsRef.current[exportIndex] = el;
              }}
              type="button"
              role="menuitem"
              tabIndex={activeIndex === exportIndex ? 0 : -1}
              aria-disabled={!canExport || exporting}
              aria-describedby={!canExport ? hintId : undefined}
              onClick={() => void handleExport()}
              className={`flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-blue-300 ${
                canExport && !exporting
                  ? "bg-blue-600 text-white hover:bg-blue-700"
                  : "cursor-not-allowed bg-slate-100 text-slate-400"
              }`}
            >
              {exporting ? "Generating…" : "Export PDF"}
            </button>
          </div>

          {!canExport && (
            <p id={hintId} className="px-2 pt-2 text-xs text-slate-400">
              Select at least one section to export.
            </p>
          )}

          {error && (
            <p role="alert" className="px-2 pt-2 text-xs text-red-600">
              {error}
            </p>
          )}

          {/* Polite status for screen readers while the PDF is generated. */}
          <span className="sr-only" aria-live="polite">
            {exporting ? "Generating report" : ""}
          </span>
        </div>
      )}
    </div>
  );
}
