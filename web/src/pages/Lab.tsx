import { useState, useCallback } from 'react';
import { FlaskConical, Play, Dna, Loader2, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { SignalEditor } from '@/components/strategy/SignalEditor';
import { MetricsCard } from '@/components/strategy/MetricsCard';
import { KlineChart } from '@/components/charts/KlineChart';
import { EquityChart } from '@/components/charts/EquityChart';
import { TradeTable } from '@/components/strategy/TradeTable';
import { runBacktest } from '@/api/strategies';
import type {
  SignalGene,
  BacktestResponse,
  BacktestTrade,
  EquityPoint,
  SymbolType,
  TimeframeType,
  TemplateType,
} from '@/types';

const SYMBOLS: SymbolType[] = ['BTCUSDT', 'ETHUSDT'];
const TIMEFRAMES: TimeframeType[] = ['1h', '4h', '1d'];
const TEMPLATES: { value: TemplateType; label: string }[] = [
  { value: 'profit_first', label: 'Profit First' },
  { value: 'steady', label: 'Steady' },
  { value: 'risk_first', label: 'Risk First' },
];

const DEFAULT_CANDLES = [
  { time: '2024-01-01', open: 42000, high: 43500, low: 41500, close: 43200 },
  { time: '2024-01-02', open: 43200, high: 44500, low: 42800, close: 44100 },
  { time: '2024-01-03', open: 44100, high: 45200, low: 43600, close: 44800 },
  { time: '2024-01-04', open: 44800, high: 46100, low: 44500, close: 45900 },
  { time: '2024-01-05', open: 45900, high: 46800, low: 45200, close: 45500 },
  { time: '2024-01-06', open: 45500, high: 46200, low: 44100, close: 44300 },
  { time: '2024-01-07', open: 44300, high: 45100, low: 43500, close: 44800 },
  { time: '2024-01-08', open: 44800, high: 46300, low: 44600, close: 46100 },
  { time: '2024-01-09', open: 46100, high: 47500, low: 45800, close: 47200 },
  { time: '2024-01-10', open: 47200, high: 48100, low: 46800, close: 47900 },
];

function generateMockResponse(): BacktestResponse {
  const baseEquity = 10000;
  const equityCurve: EquityPoint[] = DEFAULT_CANDLES.map((c, i) => {
    const factor = 1 + (i * 0.02) + (Math.random() * 0.01);
    const bmFactor = 1 + (i * 0.008);
    return {
      time: c.time,
      equity: Math.round(baseEquity * factor * 100) / 100,
      benchmark: Math.round(baseEquity * bmFactor * 100) / 100,
    };
  });

  const trades: BacktestTrade[] = [
    { trade_id: 1, entry_time: '2024-01-01', exit_time: '2024-01-03', direction: 'long', entry_price: 43200, exit_price: 44800, quantity: 0.1, pnl: 160, pnl_pct: 3.7, fee: 4.32 },
    { trade_id: 2, entry_time: '2024-01-05', exit_time: '2024-01-07', direction: 'long', entry_price: 45500, exit_price: 44800, quantity: 0.1, pnl: -70, pnl_pct: -1.54, fee: 4.55 },
    { trade_id: 3, entry_time: '2024-01-08', exit_time: '2024-01-10', direction: 'long', entry_price: 46100, exit_price: 47900, quantity: 0.1, pnl: 180, pnl_pct: 3.9, fee: 4.61 },
  ];

  return {
    result_id: 'mock_001',
    strategy_id: 'mock_strategy',
    total_return: 15.2,
    sharpe_ratio: 1.85,
    max_drawdown: -8.3,
    win_rate: 66.7,
    total_trades: 3,
    total_score: 78.5,
    dimension_scores: { profitability: 82, stability: 71, risk_control: 85, efficiency: 76 },
    equity_curve: equityCurve,
    trades_json: trades,
  };
}

export function Lab() {
  const [entrySignals, setEntrySignals] = useState<SignalGene[]>([]);
  const [exitSignals, setExitSignals] = useState<SignalGene[]>([]);
  const [symbol, setSymbol] = useState<SymbolType>('BTCUSDT');
  const [timeframe, setTimeframe] = useState<TimeframeType>('4h');
  const [stopLoss, setStopLoss] = useState(5);
  const [takeProfit, setTakeProfit] = useState(10);
  const [positionSize, setPositionSize] = useState(100);
  const [template, setTemplate] = useState<TemplateType>('steady');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [candles] = useState(DEFAULT_CANDLES);
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false);

  const handleBacktest = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const request = {
        signal_genes: [...entrySignals, ...exitSignals].map(({ id: _id, ...rest }) => rest),
        logic_genes: { entry_logic: 'AND' as const, exit_logic: 'OR' as const },
        execution_genes: { timeframe, symbol },
        risk_genes: { stop_loss: stopLoss, take_profit: takeProfit, position_size: positionSize },
        template,
      };

      const response = await runBacktest(request);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backtest failed');
      setResult(generateMockResponse());
    } finally {
      setLoading(false);
    }
  }, [entrySignals, exitSignals, timeframe, symbol, stopLoss, takeProfit, positionSize, template]);

  const handleEvolution = useCallback(() => {
    // Will be implemented in v0.12
  }, []);

  return (
    <div className="flex h-full -m-6 overflow-hidden">
      {/* Left Panel - Parameters */}
      <div
        className={`${
          leftPanelCollapsed ? 'w-10' : 'w-[380px] min-w-[380px]'
        } bg-[var(--bg-card)] border-r border-[var(--border)] flex flex-col transition-all duration-200`}
      >
        {/* Panel Toggle */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--border)]">
          {!leftPanelCollapsed && (
            <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
              <FlaskConical className="w-4 h-4" />
              Strategy Lab
            </h2>
          )}
          <button
            type="button"
            onClick={() => setLeftPanelCollapsed(!leftPanelCollapsed)}
            className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            {leftPanelCollapsed ? (
              <PanelLeftOpen className="w-4 h-4" />
            ) : (
              <PanelLeftClose className="w-4 h-4" />
            )}
          </button>
        </div>

        {!leftPanelCollapsed && (
          <div className="flex-1 overflow-y-auto p-3 space-y-4">
            {/* Entry Signals */}
            <SignalEditor
              title="Entry Signals"
              logicLabel="AND"
              signals={entrySignals}
              allowedRoles={['entry_trigger', 'entry_guard']}
              onChange={setEntrySignals}
            />

            <div className="border-t border-[var(--border)]" />

            {/* Exit Signals */}
            <SignalEditor
              title="Exit Signals"
              logicLabel="OR"
              signals={exitSignals}
              allowedRoles={['exit_trigger', 'exit_guard']}
              onChange={setExitSignals}
            />

            <div className="border-t border-[var(--border)]" />

            {/* Risk Parameters */}
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-[var(--text-primary)]">Risk Control</h3>
              <div className="grid grid-cols-3 gap-2">
                <div className="space-y-1">
                  <label className="text-xs text-[var(--text-secondary)]">Stop Loss %</label>
                  <input
                    type="number"
                    value={stopLoss}
                    onChange={(e) => setStopLoss(Number(e.target.value))}
                    className="w-full bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] rounded px-2 py-1.5 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-[var(--text-secondary)]">Take Profit %</label>
                  <input
                    type="number"
                    value={takeProfit}
                    onChange={(e) => setTakeProfit(Number(e.target.value))}
                    className="w-full bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] rounded px-2 py-1.5 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-[var(--text-secondary)]">Position %</label>
                  <input
                    type="number"
                    value={positionSize}
                    onChange={(e) => setPositionSize(Number(e.target.value))}
                    className="w-full bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] rounded px-2 py-1.5 text-xs"
                  />
                </div>
              </div>
            </div>

            <div className="border-t border-[var(--border)]" />

            {/* Execution Parameters */}
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-[var(--text-primary)]">Execution</h3>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-xs text-[var(--text-secondary)]">Symbol</label>
                  <select
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value as SymbolType)}
                    className="w-full bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] rounded px-2 py-1.5 text-xs"
                  >
                    {SYMBOLS.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs text-[var(--text-secondary)]">Timeframe</label>
                  <select
                    value={timeframe}
                    onChange={(e) => setTimeframe(e.target.value as TimeframeType)}
                    className="w-full bg-[var(--bg-primary)] text-[var(--text-primary)] border border-[var(--border)] rounded px-2 py-1.5 text-xs"
                  >
                    {TIMEFRAMES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="border-t border-[var(--border)]" />

            {/* Template Selection */}
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-[var(--text-primary)]">Score Template</h3>
              <div className="flex gap-1">
                {TEMPLATES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setTemplate(t.value)}
                    className={`flex-1 px-2 py-1.5 rounded text-xs font-medium transition-colors ${
                      template === t.value
                        ? 'bg-[var(--color-blue)] text-white'
                        : 'bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="border-t border-[var(--border)]" />

            {/* Action Buttons */}
            <div className="flex gap-2">
              <Button
                variant="primary"
                size="md"
                className="flex-1"
                onClick={handleBacktest}
                disabled={loading}
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                {loading ? 'Running...' : 'Backtest'}
              </Button>
              <Button
                variant="secondary"
                size="md"
                className="flex-1"
                onClick={handleEvolution}
              >
                <Dna className="w-4 h-4" />
                Evolution
              </Button>
            </div>

            {error && (
              <div className="text-xs text-[var(--color-loss)] bg-[var(--color-loss)]/10 rounded p-2">
                {error} (showing demo data)
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right Panel - Results */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!result ? (
          <div className="flex flex-col items-center justify-center h-full min-h-[60vh]">
            <FlaskConical className="w-16 h-16 text-[var(--text-disabled)] mb-4" />
            <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
              Strategy Lab
            </h2>
            <p className="text-[var(--text-secondary)] text-sm text-center max-w-md">
              Configure your strategy parameters on the left panel, then click Backtest to see results here.
            </p>
          </div>
        ) : (
          <>
            {/* Metrics Row */}
            <div className="grid grid-cols-5 gap-3">
              <MetricsCard
                label="Annualized Return"
                value={`${result.total_return >= 0 ? '+' : ''}${result.total_return.toFixed(1)}%`}
                color={result.total_return >= 0 ? 'profit' : 'loss'}
              />
              <MetricsCard
                label="Sharpe Ratio"
                value={result.sharpe_ratio.toFixed(2)}
                color={result.sharpe_ratio >= 1 ? 'profit' : 'warn'}
              />
              <MetricsCard
                label="Max Drawdown"
                value={`${result.max_drawdown.toFixed(1)}%`}
                color={result.max_drawdown > -10 ? 'warn' : 'loss'}
              />
              <MetricsCard
                label="Win Rate"
                value={`${result.win_rate.toFixed(1)}%`}
                color={result.win_rate >= 50 ? 'profit' : 'loss'}
              />
              <MetricsCard
                label="Score"
                value={result.total_score.toFixed(1)}
                color={result.total_score >= 70 ? 'profit' : 'info'}
              />
            </div>

            {/* K-Line Chart */}
            <KlineChart candles={candles} trades={result.trades_json} />

            {/* Equity Curve */}
            <EquityChart equityCurve={result.equity_curve} />

            {/* Trade Table */}
            <TradeTable trades={result.trades_json} />
          </>
        )}
      </div>
    </div>
  );
}
