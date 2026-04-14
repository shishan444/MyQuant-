import { X } from "lucide-react";
import { cn, formatCurrency, formatDateTime } from "@/lib/utils";
import type { TriggerRecord } from "@/types/api";

interface TriggerDetailDrawerProps {
  trigger: TriggerRecord | null;
  open: boolean;
  onClose: () => void;
}

export function TriggerDetailDrawer({
  trigger,
  open,
  onClose,
}: TriggerDetailDrawerProps) {
  if (!open || !trigger) return null;

  const formatIndicatorKey = (key: string): string => {
    const map: Record<string, string> = {
      bb_upper: "布林上轨",
      bb_middle: "布林中轨",
      bb_lower: "布林下轨",
      ema: "EMA",
      sma: "SMA",
      rsi: "RSI",
      macd: "MACD",
      volume: "成交量",
    };
    // Try partial match
    for (const [k, v] of Object.entries(map)) {
      if (key.toLowerCase().includes(k.toLowerCase())) return v;
    }
    return key;
  };

  const formatIndicatorValue = (key: string, val: number): string => {
    if (key.includes("volume")) return val.toLocaleString();
    if (key.includes("rsi") || key.includes("cci") || key.includes("mfi")) {
      return val.toFixed(2);
    }
    return formatCurrency(val);
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/40 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={cn(
          "fixed right-0 top-0 z-50 h-full w-[400px]",
          "border-l border-border-default bg-bg-surface shadow-2xl",
          "transform transition-transform duration-[250ms] ease-out",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-default px-4 py-3">
          <h3 className="text-sm font-semibold text-text-primary">
            触发详情 #{trigger.id}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-text-muted transition-colors hover:bg-white/5 hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="overflow-y-auto p-4" style={{ height: "calc(100% - 52px)" }}>
          {/* Basic info */}
          <div className="mb-4">
            <h4 className="mb-2 text-xs font-semibold text-text-muted">基本信息</h4>
            <div className="rounded-lg border border-border-default">
              <InfoRow label="时间" value={formatDateTime(trigger.time)} />
              <InfoRow
                label="价格"
                value={formatCurrency(trigger.trigger_price)}
              />
              <InfoRow
                label="结果"
                value={trigger.matched ? "符合" : "不符合"}
                valueClass={trigger.matched ? "text-profit" : "text-loss"}
              />
              <InfoRow
                label="幅度"
                value={`${trigger.change_pct >= 0 ? "+" : ""}${trigger.change_pct}%`}
                valueClass={trigger.change_pct >= 0 ? "text-profit" : "text-loss"}
              />
            </div>
          </div>

          {/* Indicator values */}
          <div className="mb-4">
            <h4 className="mb-2 text-xs font-semibold text-text-muted">
              触发时指标值
            </h4>
            <div className="rounded-lg border border-border-default">
              {Object.entries(trigger.indicator_values).length > 0 ? (
                Object.entries(trigger.indicator_values)
                  .slice(0, 8)
                  .map(([key, val]) => (
                    <InfoRow
                      key={key}
                      label={formatIndicatorKey(key)}
                      value={formatIndicatorValue(key, val)}
                    />
                  ))
              ) : (
                <div className="px-3 py-4 text-center text-xs text-text-muted">
                  暂无指标数据
                </div>
              )}
            </div>
          </div>

          {/* Local KlineChart placeholder */}
          <div className="mb-4">
            <h4 className="mb-2 text-xs font-semibold text-text-muted">
              触发点局部K线图
            </h4>
            <div className="flex h-[200px] items-center justify-center rounded-lg border border-border-default bg-[#0a0a0f]/50 text-xs text-text-muted">
              前后各10根K线 (待集成)
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function InfoRow({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border-default px-3 py-2 last:border-b-0">
      <span className="text-xs text-text-muted">{label}:</span>
      <span className={cn("font-num text-xs text-text-primary", valueClass)}>
        {value}
      </span>
    </div>
  );
}
