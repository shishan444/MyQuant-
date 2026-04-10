import ReactECharts from 'echarts-for-react';
import { X, ChevronDown, ChevronUp } from 'lucide-react';
import type { CompareResult, StrategyListItem, EquityPoint, SignalGene, RiskGenes } from '@/types';

interface ComparePanelProps {
  result: CompareResult;
  onRemoveStrategy: (id: string) => void;
  onClose: () => void;
}

// ============================================================
// Metrics comparison table
// ============================================================

interface MetricRow {
  label: string;
  getValue: (s: StrategyListItem) => number;
  format: (v: number) => string;
  higherIsBetter: boolean;
}

const METRIC_ROWS: MetricRow[] = [
  {
    label: 'Total Score',
    getValue: (s) => s.total_score,
    format: (v) => v.toFixed(1),
    higherIsBetter: true,
  },
  {
    label: 'Annualized Return',
    getValue: (s) => s.total_return,
    format: (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`,
    higherIsBetter: true,
  },
  {
    label: 'Sharpe Ratio',
    getValue: (s) => s.sharpe_ratio,
    format: (v) => v.toFixed(2),
    higherIsBetter: true,
  },
  {
    label: 'Max Drawdown',
    getValue: (s) => s.max_drawdown,
    format: (v) => `${v.toFixed(1)}%`,
    higherIsBetter: false,
  },
  {
    label: 'Win Rate',
    getValue: (s) => s.win_rate,
    format: (v) => `${v.toFixed(1)}%`,
    higherIsBetter: true,
  },
  {
    label: 'Total Trades',
    getValue: (s) => s.total_trades,
    format: (v) => String(v),
    higherIsBetter: true,
  },
  {
    label: 'Profitability',
    getValue: (s) => s.dimension_scores.profitability,
    format: (v) => v.toFixed(1),
    higherIsBetter: true,
  },
  {
    label: 'Stability',
    getValue: (s) => s.dimension_scores.stability,
    format: (v) => v.toFixed(1),
    higherIsBetter: true,
  },
  {
    label: 'Risk Control',
    getValue: (s) => s.dimension_scores.risk_control,
    format: (v) => v.toFixed(1),
    higherIsBetter: true,
  },
  {
    label: 'Efficiency',
    getValue: (s) => s.dimension_scores.efficiency,
    format: (v) => v.toFixed(1),
    higherIsBetter: true,
  },
];

function MetricsComparisonTable({
  strategies,
}: {
  strategies: StrategyListItem[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            <th className="text-left text-[var(--text-secondary)] font-medium py-2 px-3 whitespace-nowrap">
              Metric
            </th>
            {strategies.map((s) => (
              <th
                key={s.id}
                className="text-right text-[var(--text-primary)] font-medium py-2 px-3 whitespace-nowrap"
              >
                {s.short_id}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {METRIC_ROWS.map((row) => {
            const values = strategies.map(row.getValue);
            const bestIdx = row.higherIsBetter
              ? values.indexOf(Math.max(...values))
              : values.indexOf(Math.min(...values));

            return (
              <tr
                key={row.label}
                className="border-b border-[var(--border)]/50"
              >
                <td className="py-2 px-3 text-[var(--text-secondary)] whitespace-nowrap">
                  {row.label}
                </td>
                {strategies.map((s, idx) => {
                  const val = row.getValue(s);
                  const isBest = idx === bestIdx && strategies.length > 1;
                  return (
                    <td
                      key={s.id}
                      className={`py-2 px-3 text-right whitespace-nowrap font-mono ${
                        isBest
                          ? 'text-[var(--color-profit)] font-semibold'
                          : 'text-[var(--text-primary)]'
                      }`}
                    >
                      {row.format(val)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ============================================================
// Equity curve overlay chart
// ============================================================

const CURVE_COLORS = [
  '#1E88E5',
  '#7C4DFF',
  '#00C853',
  '#FFD600',
  '#FF1744',
  '#00BCD4',
];

function EquityCurveOverlay({
  strategies,
  equityCurves,
}: {
  strategies: StrategyListItem[];
  equityCurves: { strategy_id: string; curve: EquityPoint[] }[];
}) {
  const allTimes = new Set<string>();
  equityCurves.forEach((ec) => {
    ec.curve.forEach((p) => allTimes.add(p.time));
  });
  const times = Array.from(allTimes).sort();

  const series = strategies.map((s, idx) => {
    const curveData = equityCurves.find(
      (ec) => ec.strategy_id === s.id,
    );
    const equityMap = new Map<string, number>();
    if (curveData) {
      curveData.curve.forEach((p) => equityMap.set(p.time, p.equity));
    }

    return {
      name: s.short_id,
      type: 'line' as const,
      data: times.map((t) => equityMap.get(t) ?? null),
      smooth: true,
      lineStyle: {
        color: CURVE_COLORS[idx % CURVE_COLORS.length],
        width: 2,
      },
      itemStyle: {
        color: CURVE_COLORS[idx % CURVE_COLORS.length],
      },
      showSymbol: false,
      connectNulls: true,
    };
  });

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: '#21262D',
      borderColor: '#30363D',
      textStyle: { color: '#E6EDF3', fontSize: 12 },
    },
    legend: {
      data: strategies.map((s) => s.short_id),
      top: 0,
      textStyle: { color: '#8B949E', fontSize: 11 },
      itemWidth: 16,
      itemHeight: 8,
    },
    grid: {
      left: 50,
      right: 20,
      top: 35,
      bottom: 30,
    },
    xAxis: {
      type: 'category' as const,
      data: times,
      axisLine: { lineStyle: { color: '#30363D' } },
      axisLabel: { color: '#8B949E', fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value' as const,
      axisLine: { lineStyle: { color: '#30363D' } },
      axisLabel: { color: '#8B949E', fontSize: 10 },
      splitLine: { lineStyle: { color: '#21262D' } },
    },
    series,
  };

  return <ReactECharts option={option} style={{ height: 300 }} />;
}

// ============================================================
// DNA comparison section
// ============================================================

function formatSignalGenes(genes: SignalGene[]): string[] {
  if (genes.length === 0) return ['--'];
  return genes.map((g) => {
    const params = Object.entries(g.params)
      .map(([k, v]) => `${k}=${v}`)
      .join(', ');
    return `${g.indicator}(${params}) ${g.condition} ${g.threshold} [${g.role}]`;
  });
}

function formatRiskGenes(genes: RiskGenes): string[] {
  return [
    `Stop Loss: ${genes.stop_loss}%`,
    `Take Profit: ${genes.take_profit}%`,
    `Position Size: ${genes.position_size}%`,
  ];
}

function DnaComparison({ strategies }: { strategies: StrategyListItem[] }) {
  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${strategies.length}, minmax(0, 1fr))` }}>
      {strategies.map((s) => (
        <div key={s.id} className="space-y-3">
          <div className="text-sm font-medium text-[var(--text-primary)] border-b border-[var(--border)] pb-1">
            {s.short_id} - {s.symbol} / {s.timeframe}
          </div>

          {/* Entry signals */}
          <div>
            <div className="text-xs text-[var(--text-disabled)] mb-1">Entry Signals</div>
            <div className="space-y-0.5">
              {formatSignalGenes(
                s.signal_genes.filter(
                  (g) => g.role === 'entry_trigger' || g.role === 'entry_guard',
                ),
              ).map((line, i) => (
                <div key={i} className="text-xs text-[var(--text-secondary)] font-mono">
                  {line}
                </div>
              ))}
            </div>
          </div>

          {/* Exit signals */}
          <div>
            <div className="text-xs text-[var(--text-disabled)] mb-1">Exit Signals</div>
            <div className="space-y-0.5">
              {formatSignalGenes(
                s.signal_genes.filter(
                  (g) => g.role === 'exit_trigger' || g.role === 'exit_guard',
                ),
              ).map((line, i) => (
                <div key={i} className="text-xs text-[var(--text-secondary)] font-mono">
                  {line}
                </div>
              ))}
            </div>
          </div>

          {/* Risk genes */}
          <div>
            <div className="text-xs text-[var(--text-disabled)] mb-1">Risk Control</div>
            <div className="space-y-0.5">
              {formatRiskGenes(s.risk_genes).map((line, i) => (
                <div key={i} className="text-xs text-[var(--text-secondary)] font-mono">
                  {line}
                </div>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================================
// Main ComparePanel
// ============================================================

export function ComparePanel({
  result,
  onRemoveStrategy,
  onClose,
}: ComparePanelProps) {
  const { strategies, equity_curves } = result;

  const sections = [
    { key: 'metrics', title: 'Metrics Comparison', defaultOpen: true },
    { key: 'equity', title: 'Equity Curve Overlay', defaultOpen: true },
    { key: 'dna', title: 'DNA Comparison', defaultOpen: false },
  ];

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
            Compare ({strategies.length} strategies)
          </h3>
          <div className="flex gap-1">
            {strategies.map((s) => (
              <span
                key={s.id}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[var(--bg-hover)] text-xs text-[var(--text-secondary)]"
              >
                {s.short_id}
                <button
                  type="button"
                  onClick={() => onRemoveStrategy(s.id)}
                  className="hover:text-[var(--color-loss)] transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Sections */}
      <div className="p-4 space-y-4">
        <CollapsibleSection title={sections[0].title} defaultOpen={sections[0].defaultOpen}>
          <MetricsComparisonTable strategies={strategies} />
        </CollapsibleSection>

        <CollapsibleSection title={sections[1].title} defaultOpen={sections[1].defaultOpen}>
          <EquityCurveOverlay strategies={strategies} equityCurves={equity_curves} />
        </CollapsibleSection>

        <CollapsibleSection title={sections[2].title} defaultOpen={sections[2].defaultOpen}>
          <DnaComparison strategies={strategies} />
        </CollapsibleSection>
      </div>
    </div>
  );
}

// ============================================================
// Collapsible section helper
// ============================================================

import { useState, type ReactNode } from 'react';

function CollapsibleSection({
  title,
  defaultOpen,
  children,
}: {
  title: string;
  defaultOpen: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border border-[var(--border)] rounded-lg overflow-hidden">
      <button
        type="button"
        className="flex items-center justify-between w-full px-3 py-2 bg-[var(--bg-hover)] hover:bg-[var(--border)] transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span className="text-sm font-medium text-[var(--text-primary)]">
          {title}
        </span>
        {open ? (
          <ChevronUp className="w-4 h-4 text-[var(--text-secondary)]" />
        ) : (
          <ChevronDown className="w-4 h-4 text-[var(--text-secondary)]" />
        )}
      </button>
      {open && <div className="p-3">{children}</div>}
    </div>
  );
}
