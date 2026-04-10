import { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { BacktestTrade } from '@/types';

const PAGE_SIZE = 10;

interface TradeTableProps {
  trades: BacktestTrade[];
}

export function TradeTable({ trades }: TradeTableProps) {
  const [page, setPage] = useState(0);
  const totalPages = Math.max(1, Math.ceil(trades.length / PAGE_SIZE));
  const start = page * PAGE_SIZE;
  const pageTrades = trades.slice(start, start + PAGE_SIZE);

  if (trades.length === 0) {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4 text-center text-[var(--text-disabled)] text-sm">
        No trade data available
      </div>
    );
  }

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-[var(--border)] flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">
          Trade Details
        </h3>
        <span className="text-xs text-[var(--text-secondary)]">
          {trades.length} trades
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="text-left px-3 py-2 text-[var(--text-secondary)] font-medium">#</th>
              <th className="text-left px-3 py-2 text-[var(--text-secondary)] font-medium">Direction</th>
              <th className="text-left px-3 py-2 text-[var(--text-secondary)] font-medium">Entry Time</th>
              <th className="text-right px-3 py-2 text-[var(--text-secondary)] font-medium">Entry Price</th>
              <th className="text-left px-3 py-2 text-[var(--text-secondary)] font-medium">Exit Time</th>
              <th className="text-right px-3 py-2 text-[var(--text-secondary)] font-medium">Exit Price</th>
              <th className="text-right px-3 py-2 text-[var(--text-secondary)] font-medium">PnL</th>
              <th className="text-right px-3 py-2 text-[var(--text-secondary)] font-medium">PnL %</th>
              <th className="text-right px-3 py-2 text-[var(--text-secondary)] font-medium">Fee</th>
            </tr>
          </thead>
          <tbody>
            {pageTrades.map((trade) => (
              <tr
                key={trade.trade_id}
                className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-hover)] transition-colors"
              >
                <td className="px-3 py-2 text-[var(--text-secondary)]">{trade.trade_id}</td>
                <td className="px-3 py-2">
                  <span
                    className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      trade.direction === 'long'
                        ? 'bg-[var(--color-profit)]/20 text-[var(--color-profit)]'
                        : 'bg-[var(--color-loss)]/20 text-[var(--color-loss)]'
                    }`}
                  >
                    {trade.direction.toUpperCase()}
                  </span>
                </td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">{trade.entry_time}</td>
                <td className="px-3 py-2 text-right text-[var(--text-primary)]">
                  {trade.entry_price.toFixed(2)}
                </td>
                <td className="px-3 py-2 text-[var(--text-secondary)]">{trade.exit_time}</td>
                <td className="px-3 py-2 text-right text-[var(--text-primary)]">
                  {trade.exit_price.toFixed(2)}
                </td>
                <td
                  className={`px-3 py-2 text-right font-medium ${
                    trade.pnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'
                  }`}
                >
                  {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                </td>
                <td
                  className={`px-3 py-2 text-right font-medium ${
                    trade.pnl_pct >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'
                  }`}
                >
                  {trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct.toFixed(2)}%
                </td>
                <td className="px-3 py-2 text-right text-[var(--text-secondary)]">
                  {trade.fee.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-3 py-2 border-t border-[var(--border)]">
          <span className="text-xs text-[var(--text-secondary)]">
            Page {page + 1} of {totalPages}
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
