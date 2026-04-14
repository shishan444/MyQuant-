import { cn, formatPercentValue } from "@/lib/utils";

interface ReferencePanelProps {
  percentiles: Record<string, number>;
  concentration: Record<string, number[]>;
  signal_frequency: Record<string, number>;
  extremes: Array<{ change_pct: number; time: string; is_match: boolean }>;
}

const PERCENTILE_ROWS = [
  { key: "min", label: "最小", note: "(最温和)" },
  { key: "p25", label: "25%分位", note: "" },
  { key: "p50", label: "50%分位", note: "(中位数)" },
  { key: "p75", label: "75%分位", note: "(多数情况)" },
  { key: "p90", label: "90%分位", note: "(绝大多数)" },
  { key: "max", label: "最大", note: "(最极端)" },
];

function pctColor(val: number): string {
  if (val < 0) return "text-loss";
  if (val > 0) return "text-profit";
  return "text-text-primary";
}

export function ReferencePanel({
  percentiles,
  concentration,
  signal_frequency,
  extremes,
}: ReferencePanelProps) {
  const hasPercentiles = Object.keys(percentiles).length > 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Percentile table */}
      <div>
        <h4 className="mb-2 text-sm font-semibold text-text-secondary">幅度分位</h4>
        <div className="rounded-lg border border-border-default">
          {hasPercentiles ? (
            PERCENTILE_ROWS.map((row) => {
              const val = percentiles[row.key];
              if (val === undefined) return null;
              return (
                <div
                  key={row.key}
                  className="flex items-center justify-between border-b border-border-default px-3 py-1.5 last:border-b-0"
                >
                  <span className="text-xs text-text-muted">
                    {row.label}
                    {row.note && (
                      <span className="ml-1 text-[10px] text-text-muted/60">
                        {row.note}
                      </span>
                    )}
                  </span>
                  <span className={cn("font-num text-[13px] font-semibold", pctColor(val))}>
                    {formatPercentValue(val)}
                  </span>
                </div>
              );
            })
          ) : (
            <div className="px-3 py-4 text-center text-xs text-text-muted">
              暂无数据
            </div>
          )}
        </div>
      </div>

      {/* Concentration ranges */}
      {concentration.p50_range && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-text-secondary">集中区间</h4>
          <div className="flex flex-col gap-1.5">
            <p className="text-xs text-text-secondary">
              50% 触发落在{" "}
              <span className="font-num font-semibold text-text-primary">
                {formatPercentValue(concentration.p50_range[0])}
              </span>{" "}
              ~{" "}
              <span className="font-num font-semibold text-text-primary">
                {formatPercentValue(concentration.p50_range[1])}
              </span>
            </p>
            {concentration.p90_range && (
              <p className="text-xs text-text-secondary">
                90% 触发落在{" "}
                <span className="font-num font-semibold text-text-primary">
                  {formatPercentValue(concentration.p90_range[0])}
                </span>{" "}
                ~{" "}
                <span className="font-num font-semibold text-text-primary">
                  {formatPercentValue(concentration.p90_range[1])}
                </span>
              </p>
            )}
          </div>
        </div>
      )}

      {/* Signal frequency */}
      {signal_frequency.per_month !== undefined && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-text-secondary">信号频率</h4>
          <p className="text-xs text-text-secondary">
            约{" "}
            <span className="font-num text-[13px] font-semibold text-text-primary">
              {signal_frequency.per_month}
            </span>{" "}
            次/月 ({signal_frequency.total_months ?? "?"}个月)
          </p>
        </div>
      )}

      {/* Extremes */}
      {extremes.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-text-secondary">极端值</h4>
          {extremes.map((ex, i) => (
            <p key={i} className="text-xs text-text-secondary">
              最差{" "}
              <span className="font-num font-semibold text-loss">
                {formatPercentValue(ex.change_pct)}
              </span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
