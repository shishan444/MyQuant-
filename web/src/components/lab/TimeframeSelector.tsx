import { useState, useRef } from "react";
import { cn } from "@/lib/utils";
import { TIMEFRAME_SELECT_OPTIONS } from "@/lib/constants";
import { DropdownPortal } from "./DropdownPortal";

interface TimeframeSelectorProps {
  value: string;
  onChange: (v: string) => void;
  baseTimeframe: string;
}

export function TimeframeSelector({ value, onChange, baseTimeframe }: TimeframeSelectorProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const display = value || baseTimeframe;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={cn(
          "h-7 rounded-md border px-2 text-xs transition-colors",
          "border-border-default bg-bg-surface text-text-primary",
          "hover:border-accent-gold/50",
        )}
        onClick={() => setOpen(!open)}
      >
        {display.toUpperCase()}
      </button>

      <DropdownPortal triggerRef={triggerRef} open={open} onClose={() => setOpen(false)} width={120}>
        <div className="rounded-lg border border-border-default bg-bg-surface shadow-xl">
          <div className="py-1">
            {TIMEFRAME_SELECT_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={cn(
                  "flex w-full items-center px-3 py-1.5 text-xs transition-colors",
                  display === opt.value
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
      </DropdownPortal>
    </>
  );
}
