import { useState, useEffect, useMemo, useRef } from "react";
import { Loader2, AlertTriangle, Play, Dna } from "lucide-react";
import { toast } from "sonner";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/Button";
import { KlineChart } from "@/components/charts/KlineChart";
import type { KlineChartHandle, CandleData, SignalData } from "@/components/charts/KlineChart";
import { BacktestMetricsPanel } from "./BacktestMetricsPanel";
import { EquityCurveChart } from "./EquityCurveChart";
import { runBacktest } from "@/services/strategies";
import { getOhlcvBySymbol } from "@/services/datasets";
import { useCreateStrategy } from "@/hooks/useStrategies";
import { StrategyDetail } from "@/components/evolution/StrategyDetail";
import type { DNA, BacktestResult, TradeSignal } from "@/types/api";

interface BacktestModePanelProps {
  initialDna: DNA;
  initialSymbol: string;
  initialTimeframe: string;
  initialDataStart?: string;
  initialDataEnd?: string;
}

export function BacktestModePanel({
  initialDna,
  initialSymbol,
  initialTimeframe,
  initialDataStart,
  initialDataEnd,
}: BacktestModePanelProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [candles, setCandles] = useState<CandleData[]>([]);
  const chartRef = useRef<KlineChartHandle>(null);
  const saveStrategy = useCreateStrategy();
  const navigate = useNavigate();

  // Auto-run backtest on mount
  useEffect(() => {
    runBacktestAction();
  }, []);

  const datasetId = `${initialSymbol}_${initialTimeframe}`;

  function runBacktestAction() {
    setLoading(true);
    setError(null);
    setResult(null);

    Promise.all([
      runBacktest({
        dna: initialDna,
        symbol: initialSymbol,
        timeframe: initialTimeframe,
        dataset_id: datasetId,
        data_start: initialDataStart || undefined,
        data_end: initialDataEnd || undefined,
      }),
      getOhlcvBySymbol(initialSymbol, initialTimeframe, {
        start: initialDataStart || undefined,
        end: initialDataEnd || undefined,
        limit: 10000,
      }).catch(() => null),
    ])
      .then(([btResult, ohlcvData]) => {
        setResult(btResult);
        if (ohlcvData?.data) {
          setCandles(
            ohlcvData.data.map((d) => ({
              timestamp: d.timestamp,
              open: d.open,
              high: d.high,
              low: d.low,
              close: d.close,
            }))
          );
        }
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "回测失败";
        setError(msg);
      })
      .finally(() => setLoading(false));
  }

  const signals: SignalData[] = useMemo(() => {
    if (!result?.signals) return [];
    return result.signals.map((s: TradeSignal) => ({
      type: s.type,
      timestamp: s.timestamp,
    }));
  }, [result]);

  const equityPoints = useMemo(() => {
    if (!result?.equity_curve) return [];
    return result.equity_curve;
  }, [result]);

  async function handleSave() {
    try {
      await saveStrategy.mutateAsync({
        name: `${initialSymbol} ${initialTimeframe} 回测策略`,
        dna: initialDna,
        symbol: initialSymbol,
        timeframe: initialTimeframe,
        source: "lab",
        tags: "backtest,evolution",
      });
      toast.success("策略已保存");
    } catch {
      // handled by mutation
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-20">
        <Loader2 className="h-8 w-8 animate-spin text-amber-400" />
        <span className="text-sm text-slate-400">正在运行回测...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-lg border border-red-500/20 bg-red-500/5 p-8">
        <AlertTriangle className="h-8 w-8 text-red-400" />
        <p className="text-sm text-red-400">{error}</p>
        <Button variant="outline" size="sm" onClick={runBacktestAction}>
          重试
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {/* DNA summary */}
      <div>
        <h4 className="mb-2 text-xs font-medium text-slate-400">策略基因</h4>
        <StrategyDetail dna={initialDna} />
      </div>

      {/* Run / Re-run button */}
      {!result && !loading && !error && (
        <Button onClick={runBacktestAction} className="gap-2">
          <Play className="h-4 w-4" />
          运行回测
        </Button>
      )}

      {result && (
        <>
          {/* K-line chart with trade signals */}
          {candles.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-medium text-slate-400">
                K 线 + 交易信号
                <span className="ml-2 text-slate-600">
                  {initialSymbol} / {initialTimeframe}
                </span>
              </h4>
              <div className="rounded-lg border border-slate-700/30 bg-slate-950/50">
                <KlineChart
                  ref={chartRef}
                  data={candles}
                  signals={signals}
                  height={420}
                />
              </div>
              <div className="mt-1.5 flex items-center gap-4 text-[10px] text-slate-500">
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
                  买入 ({signals.filter((s) => s.type === "buy").length})
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-red-400" />
                  卖出 ({signals.filter((s) => s.type === "sell").length})
                </span>
                <span className="ml-auto">
                  {result.data_start?.slice(0, 10)} ~ {result.data_end?.slice(0, 10)}
                </span>
              </div>
            </div>
          )}

          {/* Equity curve */}
          {equityPoints.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-medium text-slate-400">资金曲线</h4>
              <div className="rounded-lg border border-slate-700/30 bg-slate-950/50 p-3">
                <EquityCurveChart data={equityPoints} />
              </div>
              <div className="mt-1.5 flex items-center gap-4 text-[10px] text-slate-500">
                <span>初始: {equityPoints[0]?.value?.toLocaleString()}</span>
                <span>最终: {equityPoints[equityPoints.length - 1]?.value?.toLocaleString()}</span>
                {result.liquidated && <span className="text-red-400">已爆仓</span>}
              </div>
            </div>
          )}

          {/* Metrics panel */}
          <div>
            <h4 className="mb-2 text-xs font-medium text-slate-400">回测指标</h4>
            <BacktestMetricsPanel result={result} />
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={runBacktestAction}
              className="text-[11px]"
            >
              重新运行
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleSave}
              disabled={saveStrategy.isPending}
              className="gap-1 text-[11px] text-amber-400"
            >
              保存策略
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/evolution", { state: { seedDna: initialDna } })}
              className="gap-1 text-[11px] text-purple-400"
            >
              <Dna className="h-3.5 w-3.5" />
              继续优化
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
