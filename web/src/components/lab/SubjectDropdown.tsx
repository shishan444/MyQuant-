import { useState, useMemo } from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface SubjectOption {
  value: string;
  label: string;
  category: string;
}

const SUBJECT_OPTIONS: SubjectOption[] = [
  { value: "close", label: "收盘价", category: "价格类" },
  { value: "price", label: "收盘价(price)", category: "价格类" },
  { value: "open", label: "开盘价", category: "价格类" },
  { value: "high", label: "最高价", category: "价格类" },
  { value: "low", label: "最低价", category: "价格类" },
  { value: "volume", label: "成交量", category: "量能类" },
  { value: "ema", label: "EMA", category: "趋势类" },
  { value: "sma", label: "SMA", category: "趋势类" },
  { value: "adx", label: "ADX", category: "趋势类" },
  { value: "rsi", label: "RSI", category: "震荡类" },
  { value: "macd", label: "MACD", category: "震荡类" },
  { value: "kdj", label: "KDJ", category: "震荡类" },
  { value: "cci", label: "CCI", category: "震荡类" },
  { value: "roc", label: "ROC", category: "震荡类" },
  { value: "bb_upper", label: "布林带上轨", category: "波动类" },
  { value: "bb_middle", label: "布林带中轨", category: "波动类" },
  { value: "bb_lower", label: "布林带下轨", category: "波动类" },
  { value: "atr", label: "ATR", category: "波动类" },
  { value: "obv", label: "OBV", category: "量能类" },
  { value: "mfi", label: "MFI", category: "量能类" },
  { value: "cmf", label: "CMF", category: "量能类" },
];

const CATEGORIES = [...new Set(SUBJECT_OPTIONS.map((o) => o.category))];

interface SubjectDropdownProps {
  value: string;
  onChange: (v: string) => void;
}

const LABEL_MAP: Record<string, string> = {};
for (const opt of SUBJECT_OPTIONS) {
  LABEL_MAP[opt.value] = opt.label;
}

export function getSubjectLabel(value: string): string {
  return LABEL_MAP[value] ?? value;
}

export function SubjectDropdown({ value, onChange }: SubjectDropdownProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search) return SUBJECT_OPTIONS;
    const q = search.toLowerCase();
    return SUBJECT_OPTIONS.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        o.value.toLowerCase().includes(q),
    );
  }, [search]);

  const currentLabel = getSubjectLabel(value);

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
          <div
            className="fixed inset-0 z-40"
            onClick={() => {
              setOpen(false);
              setSearch("");
            }}
          />
          <div
            className={cn(
              "absolute left-0 top-full z-50 mt-1 w-44",
              "rounded-lg border border-border-default bg-bg-surface shadow-xl",
            )}
          >
            <div className="flex items-center gap-2 border-b border-border-default px-2 py-1.5">
              <Search className="h-3 w-3 text-text-muted" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索指标..."
                className="w-full bg-transparent text-xs text-text-primary outline-none placeholder:text-text-muted"
                autoFocus
              />
            </div>
            <div className="max-h-56 overflow-y-auto py-1">
              {CATEGORIES.map((cat) => {
                const items = filtered.filter((o) => o.category === cat);
                if (items.length === 0) return null;
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
                          setSearch("");
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
