import { Eye, Dna, CheckSquare, Square } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { StrategyListItem } from '@/types';

interface StrategyCardProps {
  strategy: StrategyListItem;
  selected: boolean;
  onSelect: (id: string) => void;
  onView: (id: string) => void;
  onEvolve: (id: string) => void;
}

function formatScore(score: number): string {
  return score.toFixed(1);
}

function formatPercent(value: number): string {
  const prefix = value >= 0 ? '+' : '';
  return `${prefix}${value.toFixed(1)}%`;
}

function scoreColor(score: number): string {
  if (score >= 80) return 'text-[var(--color-profit)]';
  if (score >= 60) return 'text-[var(--color-info)]';
  if (score >= 40) return 'text-[var(--color-warn)]';
  return 'text-[var(--color-loss)]';
}

function returnColor(value: number): string {
  return value >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]';
}

function drawdownColor(value: number): string {
  if (value > -5) return 'text-[var(--color-profit)]';
  if (value > -10) return 'text-[var(--color-warn)]';
  return 'text-[var(--color-loss)]';
}

const TYPE_LABELS: Record<string, string> = {
  trend_following: 'Trend',
  mean_reversion: 'MR',
  breakout: 'Break',
  custom: 'Custom',
};

export function StrategyCard({
  strategy,
  selected,
  onSelect,
  onView,
  onEvolve,
}: StrategyCardProps) {
  return (
    <div
      className={`bg-[var(--bg-card)] border rounded-lg p-4 transition-colors hover:border-[var(--color-blue)]/40 ${
        selected ? 'border-[var(--color-blue)]' : 'border-[var(--border)]'
      }`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          {/* Checkbox */}
          <button
            type="button"
            onClick={() => onSelect(strategy.id)}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors shrink-0"
          >
            {selected ? (
              <CheckSquare className="w-4 h-4 text-[var(--color-blue)]" />
            ) : (
              <Square className="w-4 h-4" />
            )}
          </button>
          {/* ID + Score */}
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--text-disabled)] font-mono">
                {strategy.short_id}
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-hover)] text-[var(--text-secondary)]">
                {TYPE_LABELS[strategy.type] ?? strategy.type}
              </span>
            </div>
            <div className={`text-2xl font-bold ${scoreColor(strategy.total_score)}`}>
              {formatScore(strategy.total_score)}
            </div>
          </div>
        </div>
        {/* Symbol / Timeframe */}
        <div className="text-right">
          <div className="text-sm font-medium text-[var(--text-primary)]">
            {strategy.symbol.replace('USDT', '')}
          </div>
          <div className="text-xs text-[var(--text-secondary)]">
            {strategy.timeframe}
          </div>
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-4 gap-2 text-xs mb-3">
        <div>
          <div className="text-[var(--text-disabled)] mb-0.5">Annual</div>
          <div className={`font-medium ${returnColor(strategy.total_return)}`}>
            {formatPercent(strategy.total_return)}
          </div>
        </div>
        <div>
          <div className="text-[var(--text-disabled)] mb-0.5">Sharpe</div>
          <div className="font-medium text-[var(--text-primary)]">
            {strategy.sharpe_ratio.toFixed(2)}
          </div>
        </div>
        <div>
          <div className="text-[var(--text-disabled)] mb-0.5">Drawdown</div>
          <div className={`font-medium ${drawdownColor(strategy.max_drawdown)}`}>
            {strategy.max_drawdown.toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-[var(--text-disabled)] mb-0.5">Trades</div>
          <div className="font-medium text-[var(--text-primary)]">
            {strategy.total_trades}
          </div>
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="flex-1"
          onClick={() => onView(strategy.id)}
        >
          <Eye className="w-3.5 h-3.5" />
          View
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="flex-1"
          onClick={() => onEvolve(strategy.id)}
        >
          <Dna className="w-3.5 h-3.5" />
          Evolve
        </Button>
      </div>
    </div>
  );
}
