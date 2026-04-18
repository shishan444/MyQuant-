import { useState, useMemo, useRef } from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { DropdownPortal } from "./DropdownPortal";

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
  { value: "aroon_up", label: "Aroon Up", category: "震荡类" },
  { value: "aroon_down", label: "Aroon Down", category: "震荡类" },
  { value: "aroon_osc", label: "Aroon OSC", category: "震荡类" },
  { value: "cmo", label: "CMO", category: "震荡类" },
  { value: "trix", label: "TRIX", category: "震荡类" },
  { value: "bb_upper", label: "布林带上轨", category: "波动类" },
  { value: "bb_middle", label: "布林带中轨", category: "波动类" },
  { value: "bb_lower", label: "布林带下轨", category: "波动类" },
  { value: "atr", label: "ATR", category: "波动类" },
  { value: "obv", label: "OBV", category: "量能类" },
  { value: "mfi", label: "MFI", category: "量能类" },
  { value: "cmf", label: "CMF", category: "量能类" },
  { value: "rvol", label: "RVOL", category: "量能类" },
  { value: "vroc", label: "VROC", category: "量能类" },
  { value: "ad", label: "AD", category: "量能类" },
  { value: "cvd", label: "CVD", category: "量能类" },
  { value: "vwma", label: "VWMA", category: "量能类" },
  { value: "vp_poc", label: "VP-POC", category: "结构类" },
  { value: "vp_vah", label: "VP-VAH", category: "结构类" },
  { value: "vp_val", label: "VP-VAL", category: "结构类" },
  { value: "prev_high_n", label: "前N根最高价", category: "动态参考" },
  { value: "prev_low_n", label: "前N根最低价", category: "动态参考" },
  { value: "prev_close_avg_n", label: "前N根收盘均价", category: "动态参考" },
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
  const triggerRef = useRef<HTMLButtonElement>(null);

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

  const handleClose = () => {
    setOpen(false);
    setSearch("");
  };

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
        {currentLabel}
      </button>

      <DropdownPortal triggerRef={triggerRef} open={open} onClose={handleClose} width={176}>
        <div
          className={cn(
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
                        handleClose();
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
      </DropdownPortal>
    </>
  );
}
