import { useState } from "react";
import { cn } from "@/lib/utils";

interface TargetInputProps {
  value: string;
  onChange: (v: string) => void;
  action: string;
  subject: string;
}

const INDICATOR_TARGETS = [
  { value: "bb_upper", label: "布林带上轨" },
  { value: "bb_middle", label: "布林带中轨" },
  { value: "bb_lower", label: "布林带下轨" },
  { value: "ema", label: "EMA" },
  { value: "sma", label: "SMA" },
];

export function getTargetLabel(value: string): string {
  const found = INDICATOR_TARGETS.find((t) => t.value === value);
  if (found) return found.label;
  if (value === "" || value === undefined) return "选择参考值";
  if (!isNaN(Number(value))) return `${value}%`;
  return value;
}

function isCrossAction(action: string): boolean {
  return ["touch", "cross_above", "cross_below", "breakout", "breakdown"].includes(action);
}

function isMultiplierAction(action: string): boolean {
  return ["spike", "shrink"].includes(action);
}

export function TargetInput({ value, onChange, action, subject: _subject }: TargetInputProps) {
  const [open, setOpen] = useState(false);

  // Form A: cross/touch/breakout/breakdown -> select indicator line
  if (isCrossAction(action)) {
    const currentLabel = INDICATOR_TARGETS.find((t) => t.value === value)?.label ?? "选择参考值";

    return (
      <div className="relative">
        <button
          type="button"
          className={cn(
            "h-7 rounded-md border px-2 text-xs transition-colors",
            "border-border-default bg-bg-surface text-text-primary",
            "hover:border-accent-gold/50",
          )}
          onClick={() => setOpen(!open)}
        >
          {currentLabel}
        </button>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <div
              className={cn(
                "absolute left-0 top-full z-50 mt-1 w-36",
                "rounded-lg border border-border-default bg-bg-surface shadow-xl",
              )}
            >
              <div className="py-1">
                {INDICATOR_TARGETS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={cn(
                      "flex w-full items-center px-3 py-1.5 text-xs transition-colors",
                      value === opt.value
                        ? "bg-accent-gold/10 text-accent-gold"
                        : "text-text-primary hover:bg-white/5",
                    )}
                    onClick={() => {
                      onChange(opt.value);
                      setOpen(false);
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    );
  }

  // Form C: spike/shrink -> multiplier input
  if (isMultiplierAction(action)) {
    const numVal = value || "2";
    return (
      <div className="flex items-center gap-1">
        <span className="text-xs text-text-muted">&gt;=</span>
        <input
          type="number"
          value={numVal}
          onChange={(e) => onChange(e.target.value)}
          className="h-7 w-12 rounded-md border border-border-default bg-bg-surface px-1.5 text-xs text-text-primary text-center outline-none focus:border-accent-gold"
          min="0.1"
          step="0.5"
        />
        <span className="text-xs text-text-muted">倍均量</span>
      </div>
    );
  }

  // Form B: gt/lt -> number input with % or absolute
  const numVal = value || "0";
  return (
    <div className="flex items-center gap-1">
      <span className="text-xs text-text-muted">
        {action === "gt" || action === "rise" ? ">=" : "<="}
      </span>
      <input
        type="number"
        value={numVal}
        onChange={(e) => onChange(e.target.value)}
        className="h-7 w-14 rounded-md border border-border-default bg-bg-surface px-1.5 text-xs text-text-primary text-center outline-none focus:border-accent-gold"
        step="0.5"
      />
      <span className="text-xs text-text-muted">%</span>
    </div>
  );
}
