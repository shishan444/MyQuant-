import { StatCard } from "@/components/StatCard";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";

interface MetricsData {
  total_return_pct: number;
  total_pnl: number;
  win_rate: number;
  profit_factor: number | null;
  max_drawdown_pct: number;
  avg_trade_pnl: number;
  total_trades: number;
  win_count: number;
  loss_count: number;
}

interface MetricsDashboardProps {
  metrics: MetricsData | undefined;
  initialCash: number;
}

function getTrend(value: number) {
  if (value > 0) return "up" as const;
  if (value < 0) return "down" as const;
  return "neutral" as const;
}

export function MetricsDashboard({ metrics, initialCash }: MetricsDashboardProps) {
  if (!metrics) {
    return (
      <div className="grid grid-cols-3 gap-2 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <StatCard key={i} label="--" value="--" />
        ))}
      </div>
    );
  }

  const items = [
    {
      label: "Total PnL",
      value: formatCurrency(metrics.total_pnl),
      trend: getTrend(metrics.total_pnl),
    },
    {
      label: "Return",
      value: formatPercent(metrics.total_return_pct / 100),
      trend: getTrend(metrics.total_return_pct),
    },
    {
      label: "Win Rate",
      value: `${(metrics.win_rate * 100).toFixed(1)}%`,
      trend: metrics.win_rate >= 0.5 ? "up" : "down",
    },
    {
      label: "Profit Factor",
      value: metrics.profit_factor != null ? metrics.profit_factor.toFixed(2) : "N/A",
      trend: (metrics.profit_factor ?? 0) >= 1 ? "up" : "down",
    },
    {
      label: "Max Drawdown",
      value: `-${metrics.max_drawdown_pct.toFixed(1)}%`,
      trend: "down",
    },
    {
      label: "Trades",
      value: `${metrics.win_count}W / ${metrics.loss_count}L`,
      trend: "neutral" as const,
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-2 lg:grid-cols-6">
      {items.map((item) => (
        <StatCard
          key={item.label}
          label={item.label}
          value={item.value}
          trend={item.trend}
        />
      ))}
    </div>
  );
}
