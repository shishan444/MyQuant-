import { useState, useMemo } from "react";
import { cn } from "@/lib/utils";

interface ActionOption {
  value: string;
  label: string;
  category: string;
}

const PRICE_ACTIONS: ActionOption[] = [
  { value: "touch", label: "触及", category: "穿越类" },
  { value: "cross_above", label: "上穿", category: "穿越类" },
  { value: "cross_below", label: "下穿", category: "穿越类" },
  { value: "breakout", label: "突破", category: "突破类" },
  { value: "breakdown", label: "跌破", category: "突破类" },
  { value: "gt", label: "大于", category: "比较类" },
  { value: "lt", label: "小于", category: "比较类" },
  { value: "ge", label: "大于等于", category: "比较类" },
  { value: "le", label: "小于等于", category: "比较类" },
];

const VOLUME_ACTIONS: ActionOption[] = [
  { value: "spike", label: "放量", category: "量能" },
  { value: "shrink", label: "缩量", category: "量能" },
  { value: "gt", label: "大于", category: "比较" },
  { value: "lt", label: "小于", category: "比较" },
];

const INDICATOR_ACTIONS: ActionOption[] = [
  { value: "gt", label: "大于", category: "比较类" },
  { value: "lt", label: "小于", category: "比较类" },
  { value: "ge", label: "大于等于", category: "比较类" },
  { value: "le", label: "小于等于", category: "比较类" },
  { value: "cross_above", label: "上穿", category: "穿越类" },
  { value: "cross_below", label: "下穿", category: "穿越类" },
  { value: "touch", label: "触及", category: "穿越类" },
];

const THEN_DIRECTION_ACTIONS: ActionOption[] = [
  { value: "drop", label: "下跌", category: "方向" },
  { value: "rise", label: "上涨", category: "方向" },
];

function getActionsForSubject(subject: string, isThen: boolean): ActionOption[] {
  if (isThen) {
    if (subject === "close" || subject === "price" || subject === "open" || subject === "high" || subject === "low") {
      return THEN_DIRECTION_ACTIONS;
    }
    return INDICATOR_ACTIONS;
  }

  if (["close", "open", "high", "low", "price"].includes(subject)) {
    return PRICE_ACTIONS;
  }
  if (subject === "volume") {
    return VOLUME_ACTIONS;
  }
  return INDICATOR_ACTIONS;
}

const LABEL_MAP: Record<string, string> = {};
const allActions = [...PRICE_ACTIONS, ...VOLUME_ACTIONS, ...INDICATOR_ACTIONS, ...THEN_DIRECTION_ACTIONS];
for (const opt of allActions) {
  LABEL_MAP[opt.value] = opt.label;
}

export function getActionLabel(value: string): string {
  return LABEL_MAP[value] ?? value;
}

interface ActionDropdownProps {
  value: string;
  onChange: (v: string) => void;
  subject: string;
  isThen?: boolean;
}

export function ActionDropdown({ value, onChange, subject, isThen = false }: ActionDropdownProps) {
  const [open, setOpen] = useState(false);

  const actions = useMemo(() => getActionsForSubject(subject, isThen), [subject, isThen]);
  const categories = useMemo(
    () => [...new Set(actions.map((a) => a.category))],
    [actions],
  );

  const currentLabel = getActionLabel(value);

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
            <div className="max-h-48 overflow-y-auto py-1">
              {categories.map((cat) => {
                const items = actions.filter((a) => a.category === cat);
                return (
                  <div key={cat}>
                    <div className="px-2 py-1 text-[10px] font-semibold text-text-muted">
                      {cat}
                    </div>
                    {items.map((opt) => (
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
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
