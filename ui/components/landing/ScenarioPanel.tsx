"use client";

// ─── types & defaults ─────────────────────────────────────────────────────────

export interface ScenarioValues {
  height_m: number;
  total_units: number;
  affordable_units: number;
}

export const SCENARIO_DEFAULTS: ScenarioValues = {
  height_m: 45,
  total_units: 120,
  affordable_units: 12,
};

interface Props {
  values: ScenarioValues;
  onChange: (v: ScenarioValues) => void;
  /** Whether the custom values will actually be sent to the analysis. */
  enabled: boolean;
  /** Called when the user toggles the "apply" switch. */
  onToggle: () => void;
}

// ─── toggle switch ────────────────────────────────────────────────────────────

function ToggleSwitch({
  enabled,
  onToggle,
}: {
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      onClick={onToggle}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
        enabled ? "bg-blue-600" : "bg-slate-300"
      }`}
    >
      <span className="sr-only">Use custom scenario assumptions</span>
      {/* bg-gray-100 is intentionally used here instead of bg-white.
          globals.css overrides bg-white to a dark color in dark mode,
          which would make the thumb invisible against the dark track. */}
      <span
        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-gray-100 shadow ring-0 transition duration-200 ease-in-out ${
          enabled ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

// ─── field sub-component ──────────────────────────────────────────────────────

interface FieldProps {
  label: string;
  value: number;
  min: number;
  max: number;
  unit?: string;
  disabled: boolean;
  onChange: (raw: string) => void;
}

function Field({ label, value, min, max, unit, disabled, onChange }: FieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <div className="relative">
        <input
          type="number"
          inputMode="numeric"
          min={min}
          max={max}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full rounded-xl border py-2.5 text-sm font-semibold transition-all duration-150 focus:outline-none ${
            unit ? "pl-3 pr-8" : "px-3"
          } ${
            disabled
              ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
              : "border-slate-300 bg-white text-slate-800 focus:border-blue-400 focus:ring-2 focus:ring-blue-400/25"
          }`}
        />
        {unit && (
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-slate-400">
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}

// ─── panel ────────────────────────────────────────────────────────────────────

export default function ScenarioPanel({
  values,
  onChange,
  enabled,
  onToggle,
}: Props) {
  function set(key: keyof ScenarioValues, raw: string) {
    const n = parseInt(raw, 10);
    if (!Number.isFinite(n) || n < 0) return;
    onChange({ ...values, [key]: n });
  }

  return (
    <div
      className={`rounded-2xl border p-5 shadow-sm transition-colors duration-200 ${
        enabled
          ? "border-blue-200 bg-blue-50"
          : "border-slate-200 bg-white"
      }`}
    >
      {/* Header — toggle row */}
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-800">
            Custom scenario assumptions
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            {enabled
              ? "Custom values will be applied to your analysis"
              : "Off — analysis will use system defaults"}
          </p>
        </div>
        <ToggleSwitch enabled={enabled} onToggle={onToggle} />
      </div>

      {/* Inputs — always visible but disabled when toggle is OFF */}
      <div
        className={`mt-4 grid grid-cols-3 gap-3 transition-opacity duration-200 ${
          enabled ? "opacity-100" : "opacity-40"
        }`}
      >
        <Field
          label="Height"
          unit="m"
          value={values.height_m}
          min={12}
          max={100}
          disabled={!enabled}
          onChange={(v) => set("height_m", v)}
        />
        <Field
          label="Total units"
          value={values.total_units}
          min={1}
          max={500}
          disabled={!enabled}
          onChange={(v) => set("total_units", v)}
        />
        <Field
          label="Affordable units"
          value={values.affordable_units}
          min={0}
          max={values.total_units}
          disabled={!enabled}
          onChange={(v) => set("affordable_units", v)}
        />
      </div>
    </div>
  );
}
