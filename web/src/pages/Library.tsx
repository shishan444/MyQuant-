import { useState, useCallback } from 'react';
import { Search, Loader2, AlertCircle, BookOpen } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/Button';
import { StrategyCard } from '@/components/strategy/StrategyCard';
import { ComparePanel } from '@/components/strategy/ComparePanel';
import { listStrategies, compareStrategies } from '@/api/strategies';
import type {
  StrategyListItem,
  StrategyListParams,
  StrategySortField,
  SortOrder,
  SymbolType,
  TimeframeType,
  StrategySource,
  CompareResult,
} from '@/types';

const SYMBOL_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All Pairs' },
  { value: 'BTCUSDT', label: 'BTC' },
  { value: 'ETHUSDT', label: 'ETH' },
];

const TIMEFRAME_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All TF' },
  { value: '1h', label: '1H' },
  { value: '4h', label: '4H' },
  { value: '1d', label: '1D' },
];

const SOURCE_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'manual', label: 'Manual' },
  { value: 'evolution', label: 'Evolved' },
  { value: 'import', label: 'Imported' },
];

const SORT_OPTIONS: { value: StrategySortField; label: string }[] = [
  { value: 'total_score', label: 'Score' },
  { value: 'total_return', label: 'Return' },
  { value: 'sharpe_ratio', label: 'Sharpe' },
  { value: 'max_drawdown', label: 'Drawdown' },
  { value: 'created_at', label: 'Date' },
];

// ============================================================
// Mock data generator for demo / fallback
// ============================================================

function generateMockStrategies(): StrategyListItem[] {
  const symbols: SymbolType[] = ['BTCUSDT', 'ETHUSDT'];
  const timeframes: TimeframeType[] = ['1h', '4h', '1d'];
  const sources: StrategySource[] = ['manual', 'evolution', 'import'];

  return Array.from({ length: 12 }, (_, i) => {
    const id = `strat_${String(i + 1).padStart(3, '0')}`;
    return {
      id,
      short_id: id.slice(0, 7),
      name: `Strategy ${i + 1}`,
      description: `Generated strategy #${i + 1}`,
      type: (['trend_following', 'mean_reversion', 'breakout', 'custom'] as const)[i % 4],
      source: sources[i % 3],
      symbol: symbols[i % 2],
      timeframe: timeframes[i % 3],
      total_score: 40 + Math.random() * 55,
      total_return: -15 + Math.random() * 60,
      sharpe_ratio: 0.3 + Math.random() * 2.5,
      max_drawdown: -(3 + Math.random() * 20),
      total_trades: Math.floor(10 + Math.random() * 200),
      win_rate: 30 + Math.random() * 40,
      dimension_scores: {
        profitability: 40 + Math.random() * 55,
        stability: 40 + Math.random() * 55,
        risk_control: 40 + Math.random() * 55,
        efficiency: 40 + Math.random() * 55,
      },
      signal_genes: [],
      risk_genes: {
        stop_loss: 3 + Math.random() * 7,
        take_profit: 5 + Math.random() * 15,
        position_size: 50 + Math.random() * 50,
      },
      created_at: new Date(Date.now() - i * 86400000).toISOString(),
      updated_at: new Date(Date.now() - i * 86400000).toISOString(),
    };
  });
}

// ============================================================
// Library page
// ============================================================

export function Library() {
  // Filter state
  const [search, setSearch] = useState('');
  const [symbol, setSymbol] = useState('');
  const [timeframe, setTimeframe] = useState('');
  const [source, setSource] = useState('');
  const [sortField, setSortField] = useState<StrategySortField>('total_score');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Compare state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);

  // Fetch strategies
  const params: StrategyListParams = {
    symbol: (symbol || undefined) as SymbolType | undefined,
    timeframe: (timeframe || undefined) as TimeframeType | undefined,
    source: (source || undefined) as StrategySource | undefined,
    sort_by: sortField,
    sort_order: sortOrder,
    search: search || undefined,
    page,
    page_size: pageSize,
  };

  const {
    data: response,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['strategies-list', params],
    queryFn: () => listStrategies(params),
    placeholderData: (prev) => prev,
  });

  // Use mock data on error or when API not available
  const strategies: StrategyListItem[] =
    response?.items ?? (error ? generateMockStrategies() : []);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleCompare = useCallback(async () => {
    if (selectedIds.size < 2) return;
    setCompareLoading(true);
    try {
      const result = await compareStrategies(Array.from(selectedIds));
      setCompareResult(result);
    } catch {
      // Build a mock compare result from current strategies
      const selected = strategies.filter((s) => selectedIds.has(s.id));
      setCompareResult({
        strategies: selected,
        equity_curves: selected.map((s) => ({
          strategy_id: s.id,
          curve: Array.from({ length: 30 }, (_, i) => ({
            time: new Date(Date.now() - (29 - i) * 86400000)
              .toISOString()
              .slice(0, 10),
            equity: 10000 * (1 + (s.total_return / 100) * (i / 29)),
            benchmark: 10000 * (1 + 0.05 * (i / 29)),
          })),
        })),
      });
    } finally {
      setCompareLoading(false);
    }
  }, [selectedIds, strategies]);

  const handleRemoveFromCompare = useCallback(
    (id: string) => {
      const next = new Set(selectedIds);
      next.delete(id);
      setSelectedIds(next);
      if (next.size < 2) {
        setCompareResult(null);
      } else if (compareResult) {
        setCompareResult({
          ...compareResult,
          strategies: compareResult.strategies.filter((s) => s.id !== id),
          equity_curves: compareResult.equity_curves.filter(
            (ec) => ec.strategy_id !== id,
          ),
        });
      }
    },
    [selectedIds, compareResult],
  );

  const handleView = useCallback((_id: string) => {
    // Will navigate to strategy detail in future version
  }, []);

  const handleEvolve = useCallback((_id: string) => {
    // Will navigate to evolution page in future version
  }, []);

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Search */}
        <div className="relative w-60">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-disabled)]" />
          <input
            type="text"
            placeholder="Search strategies..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full h-9 pl-9 pr-3 bg-[var(--bg-card)] border border-[var(--border)] rounded-md text-sm text-[var(--text-primary)] placeholder:text-[var(--text-disabled)] focus:outline-none focus:border-[var(--color-blue)]"
          />
        </div>

        {/* Symbol filter */}
        <select
          value={symbol}
          onChange={(e) => {
            setSymbol(e.target.value);
            setPage(1);
          }}
          className="h-9 px-3 bg-[var(--bg-card)] border border-[var(--border)] rounded-md text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--color-blue)]"
        >
          {SYMBOL_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Timeframe filter */}
        <select
          value={timeframe}
          onChange={(e) => {
            setTimeframe(e.target.value);
            setPage(1);
          }}
          className="h-9 px-3 bg-[var(--bg-card)] border border-[var(--border)] rounded-md text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--color-blue)]"
        >
          {TIMEFRAME_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Source filter */}
        <select
          value={source}
          onChange={(e) => {
            setSource(e.target.value);
            setPage(1);
          }}
          className="h-9 px-3 bg-[var(--bg-card)] border border-[var(--border)] rounded-md text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--color-blue)]"
        >
          {SOURCE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Sort */}
        <select
          value={sortField}
          onChange={(e) => setSortField(e.target.value as StrategySortField)}
          className="h-9 px-3 bg-[var(--bg-card)] border border-[var(--border)] rounded-md text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--color-blue)]"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Sort order toggle */}
        <button
          type="button"
          onClick={() =>
            setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
          }
          className="h-9 px-3 bg-[var(--bg-card)] border border-[var(--border)] rounded-md text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          {sortOrder === 'desc' ? 'DESC' : 'ASC'}
        </button>

        {/* Compare button */}
        <div className="ml-auto">
          <Button
            variant={selectedIds.size >= 2 ? 'primary' : 'secondary'}
            size="md"
            disabled={selectedIds.size < 2 || compareLoading}
            onClick={handleCompare}
          >
            {compareLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : null}
            Compare ({selectedIds.size})
          </Button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-2 text-[var(--color-warn)] p-3 bg-[var(--color-warn)]/10 rounded-md text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>
            API unavailable - showing demo data
          </span>
        </div>
      )}

      {/* Loading state */}
      {isLoading && !error && (
        <div className="flex items-center justify-center py-16 gap-2 text-[var(--text-secondary)]">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading strategies...</span>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && strategies.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16">
          <BookOpen className="w-12 h-12 text-[var(--text-disabled)] mb-3" />
          <p className="text-[var(--text-secondary)] text-sm mb-1">
            {search ? 'No matching strategies found' : 'No strategies yet'}
          </p>
          <p className="text-[var(--text-disabled)] text-xs">
            Create strategies in the Lab or evolve them
          </p>
        </div>
      )}

      {/* Strategy card grid */}
      {!isLoading && strategies.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {strategies.map((s) => (
            <StrategyCard
              key={s.id}
              strategy={s}
              selected={selectedIds.has(s.id)}
              onSelect={toggleSelect}
              onView={handleView}
              onEvolve={handleEvolve}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {response && response.total > pageSize && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Prev
          </Button>
          <span className="text-sm text-[var(--text-secondary)]">
            Page {page} of {Math.ceil(response.total / pageSize)}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page * pageSize >= response.total}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}

      {/* Compare panel */}
      {compareResult && compareResult.strategies.length >= 2 && (
        <ComparePanel
          result={compareResult}
          onRemoveStrategy={handleRemoveFromCompare}
          onClose={() => {
            setCompareResult(null);
            setSelectedIds(new Set());
          }}
        />
      )}
    </div>
  );
}
