import { cn, formatNumber } from "@/lib/utils";
import type { BacktestResult } from "@/types/api";

interface BacktestMetricsPanelProps {
  result: BacktestResult;
}

export function BacktestMetricsPanel({ result }: BacktestMetricsPanelProps) {
  const items = [
    {
      label: "总收益",
      value: `${(result.total_return * 100).toFixed(2)}%`,
      color: result.total_return > 0 ? "text-emerald-400" : "text-red-400",
    },
    {
      label: "夏普比率",
      value: formatNumber(result.sharpe_ratio),
      color: result.sharpe_ratio > 1 ? "text-emerald-400" : result.sharpe_ratio > 0 ? "text-amber-400" : "text-red-400",
    },
    {
      label: "最大回撤",
      value: `${(result.max_drawdown * 100).toFixed(2)}%`,
      color: Math.abs(result.max_drawdown) < 0.1 ? "text-emerald-400" : Math.abs(result.max_drawdown) < 0.3 ? "text-amber-400" : "text-red-400",
    },
    {
      label: "胜率",
      value: `${(result.win_rate * 100).toFixed(1)}%`,
      color: result.win_rate > 0.5 ? "text-emerald-400" : result.win_rate > 0.3 ? "text-amber-400" : "text-red-400",
    },
    {
      label: "交易次数",
      value: String(result.total_trades),
      color: result.total_trades > 10 ? "text-slate-200" : "text-amber-400",
    },
    {
      label: "评分",
      value: formatNumber(result.total_score),
      color: result.total_score > 60 ? "text-emerald-400" : result.total_score > 40 ? "text-amber-400" : "text-red-400",
    },
  ];

  return (
    <div>
      <div className="grid grid-cols-3 gap-2">
        {items.map((item) => (
          <div
            key={item.label}
            className="rounded-lg border border-slate-700/30 bg-white/[0.02] p-3 text-center"
          >
            <div className="text-[11px] text-slate-500">{item.label}</div>
            <div className={cn("mt-1 text-sm font-mono", item.color)}>
              {item.value}
            </div>
          </div>
        ))}
      </div>
      {result.total_funding_cost > 0 && (
        <div className="mt-2 text-[11px] text-amber-500/80">
          资金费用: {formatNumber(result.total_funding_cost)}
        </div>
      )}
      {result.liquidated && (
        <div className="mt-1 text-[11px] text-red-400">
          策略触发爆仓，资金曲线已清零
        </div>
      )}
    </div>
  );
}
