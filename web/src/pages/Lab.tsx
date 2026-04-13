import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Play, Save, Download, BarChart3 } from "lucide-react";
import { toast } from "sonner";
import { GlassCard } from "@/components/GlassCard";
import { StatCard } from "@/components/StatCard";
import { KlineChart } from "@/components/charts/KlineChart";
import { ChartLegend } from "@/components/charts/ChartLegend";
import { PageTransition } from "@/components/PageTransition";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useLabStore } from "@/stores/lab";
import { useRunBacktest, useCreateStrategy } from "@/hooks/useStrategies";
import { formatPercent, formatCurrency, formatNumber } from "@/lib/utils";
import type { BacktestResult, TradeSignal, Dataset } from "@/types/api";
import type { LegendItem } from "@/types/chart";
import { TIMEFRAME_OPTIONS } from "@/types/strategy";
import { api } from "@/services/api";

const INDICATOR_BADGES = [
  { id: "ema100", type: "EMA", period: 100, color: "#1E88E5" },
  { id: "ema50", type: "EMA", period: 50, color: "#FF9800" },
  { id: "rsi14", type: "RSI", period: 14, color: "#7C4DFF" },
] as const;

function buildDefaultDNA(symbol: string, timeframe: string) {
  return {
    signal_genes: [
      {
        indicator: "EMA",
        params: { period: 20 },
        role: "entry_trigger",
        condition: { type: "price_above" },
      },
      {
        indicator: "EMA",
        params: { period: 20 },
        role: "exit_trigger",
        condition: { type: "price_below" },
      },
    ],
    logic_genes: { entry_logic: "AND", exit_logic: "AND" },
    execution_genes: { timeframe, symbol },
    risk_genes: { stop_loss: 0.03, take_profit: 0.06, position_size: 1.0 },
    generation: 0,
    parent_ids: [],
    mutation_ops: [],
  };
}

export function Lab() {
  const config = useLabStore((s) => s.config);
  const setConfig = useLabStore((s) => s.setConfig);

  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [legendItems] = useState<LegendItem[]>([
    { id: "kline", label: "K线", color: "#94a3b8", visible: true },
    ...INDICATOR_BADGES.map((ind) => ({
      id: ind.id,
      label: `${ind.type}(${ind.period})`,
      color: ind.color,
      visible: true,
    })),
  ]);

  // 数据集列表
  const { data: datasetsData } = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api.get("/api/data/datasets").then((r) => r.data),
  });

  // OHLCV 数据
  const { data: ohlcvData, isLoading: ohlcvLoading } = useQuery({
    queryKey: ["ohlcv", config.datasetId],
    queryFn: () =>
      api.get(`/api/data/datasets/${config.datasetId}/ohlcv`).then((r) => r.data),
    enabled: !!config.datasetId,
  });

  const runBacktest = useRunBacktest();
  const createStrategy = useCreateStrategy();

  const handleRunBacktest = useCallback(async () => {
    if (!config.datasetId) {
      toast.error("请先选择数据集");
      return;
    }
    try {
      const result = await runBacktest.mutateAsync({
        dna: buildDefaultDNA(config.symbol, config.timeframe),
        symbol: config.symbol,
        timeframe: config.timeframe,
        dataset_id: config.datasetId,
        score_template: config.scoreTemplate,
        init_cash: config.initCash,
        fee: config.fee,
        slippage: config.slippage,
      });
      setBacktestResult(result);
    } catch {
      // handled by mutation onError
    }
  }, [config, runBacktest]);

  const handleSaveStrategy = useCallback(async () => {
    if (!backtestResult) return;
    try {
      await createStrategy.mutateAsync({
        name: `${config.symbol} ${config.timeframe} 策略`,
        dna: buildDefaultDNA(config.symbol, config.timeframe),
        symbol: config.symbol,
        timeframe: config.timeframe,
        source: "lab",
      });
    } catch {
      // handled
    }
  }, [backtestResult, config, createStrategy]);

  const toggleLegend = useCallback((id: string) => {
    void id;
    // TODO: integrate with chart series visibility
  }, []);

  const datasets: Dataset[] = datasetsData?.datasets ?? datasetsData?.items ?? [];
  const chartData =
    ohlcvData?.data?.map(
      (d: { timestamp: string; open: number; high: number; low: number; close: number }) => ({
        timestamp: d.timestamp,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      })
    ) ?? [];
  const chartSignals = backtestResult?.signals ?? [];

  const stats = backtestResult
    ? [
        {
          label: "年化收益",
          value: formatPercent(backtestResult.total_return),
          trend: (backtestResult.total_return >= 0 ? "up" : "down") as "up" | "down" | "neutral",
        },
        {
          label: "夏普比率",
          value: formatNumber(backtestResult.sharpe_ratio),
          trend: (backtestResult.sharpe_ratio >= 1 ? "up" : "neutral") as "up" | "down" | "neutral",
        },
        {
          label: "最大回撤",
          value: formatPercent(backtestResult.max_drawdown),
          trend: (backtestResult.max_drawdown <= -0.15 ? "down" : "neutral") as "up" | "down" | "neutral",
        },
        {
          label: "胜率",
          value: formatPercent(backtestResult.win_rate),
          trend: (backtestResult.win_rate >= 0.5 ? "up" : "down") as "up" | "down" | "neutral",
        },
        {
          label: "交易笔数",
          value: String(backtestResult.total_trades),
          trend: "neutral" as "up" | "down" | "neutral",
        },
      ]
    : null;

  return (
    <PageTransition>
      <div className="flex flex-col gap-4">
        {/* 配置区 */}
        <GlassCard className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-secondary">数据:</span>
              <Select
                value={config.datasetId || "__none__"}
                onValueChange={(v) => {
                  const ds = datasets.find((d) => d.dataset_id === v);
                  setConfig({
                    datasetId: v === "__none__" ? "" : v,
                    symbol: ds?.symbol ?? config.symbol,
                  });
                }}
              >
                <SelectTrigger className="w-44 h-8 text-xs">
                  <SelectValue placeholder="选择数据集" />
                </SelectTrigger>
                <SelectContent>
                  {datasets.map((ds) => (
                    <SelectItem key={ds.dataset_id} value={ds.dataset_id}>
                      {ds.symbol} ({ds.interval})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-text-secondary">周期:</span>
              <Select value={config.timeframe} onValueChange={(v) => setConfig({ timeframe: v })}>
                <SelectTrigger className="w-28 h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIMEFRAME_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-text-secondary">评分:</span>
              <Select value={config.scoreTemplate} onValueChange={(v) => setConfig({ scoreTemplate: v })}>
                <SelectTrigger className="w-32 h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="profit_first">收益优先</SelectItem>
                  <SelectItem value="steady">稳健优先</SelectItem>
                  <SelectItem value="risk_first">风控优先</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {INDICATOR_BADGES.map((ind) => (
              <Badge key={ind.id} variant="outline" className="h-7 text-xs gap-1 border-border-default">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: ind.color }} />
                {ind.type}({ind.period})
              </Badge>
            ))}

            <div className="ml-auto">
              <Button
                size="sm"
                onClick={handleRunBacktest}
                disabled={runBacktest.isPending || !config.datasetId}
                className="gap-1.5 bg-accent-gold text-black hover:bg-accent-gold/90"
              >
                <Play className="h-3.5 w-3.5" />
                {runBacktest.isPending ? "回测中..." : "运行回测"}
              </Button>
            </div>
          </div>
        </GlassCard>

        {/* K线图区 */}
        <GlassCard className="p-4" hover={false}>
          <ChartLegend
            items={legendItems}
            onToggle={toggleLegend}
            extra={
              <span className="text-xs text-text-muted">
                {config.symbol} / {config.timeframe}
              </span>
            }
          />
          <div className="mt-2">
            {ohlcvLoading ? (
              <Skeleton className="h-[450px] w-full rounded-lg" />
            ) : chartData.length > 0 ? (
              <KlineChart data={chartData} signals={chartSignals} height={450} />
            ) : (
              <div className="flex h-[450px] items-center justify-center rounded-lg bg-[#0a0a0f]/50">
                <p className="text-sm text-text-muted">
                  {config.datasetId ? "加载中..." : "请选择数据集以查看K线图"}
                </p>
              </div>
            )}
          </div>
        </GlassCard>

        {/* 回测统计 */}
        {stats && (
          <GlassCard className="p-4" hover={false}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-text-secondary">回测统计</h3>
              <Button
                size="sm"
                variant="outline"
                onClick={handleSaveStrategy}
                disabled={createStrategy.isPending}
                className="gap-1.5 border-accent-gold/30 text-accent-gold hover:bg-accent-gold/10"
              >
                <Save className="h-3.5 w-3.5" />
                保存到策略库
              </Button>
            </div>
            <div className="mt-3 grid grid-cols-5 gap-3">
              {stats.map((stat) => (
                <StatCard key={stat.label} {...stat} />
              ))}
            </div>
          </GlassCard>
        )}

        {/* 交易信号 */}
        {backtestResult && backtestResult.total_trades > 0 && (
          <GlassCard className="p-4" hover={false}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-text-secondary">
                交易信号 ({backtestResult.total_trades}笔)
              </h3>
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" className="gap-1 text-xs text-text-secondary">
                  <Download className="h-3.5 w-3.5" />
                  导出
                </Button>
                <Button size="sm" variant="ghost" className="gap-1 text-xs text-text-secondary">
                  <BarChart3 className="h-3.5 w-3.5" />
                  详细分析
                </Button>
              </div>
            </div>
            <ScrollArea className="mt-3 h-64">
              <div className="flex flex-col gap-1.5">
                {(backtestResult.signals ?? []).slice(0, 20).map((signal, i) => (
                  <TradeSignalRow key={i} signal={signal} />
                ))}
              </div>
            </ScrollArea>
          </GlassCard>
        )}
      </div>
    </PageTransition>
  );
}

function TradeSignalRow({ signal }: { signal: TradeSignal }) {
  const isBuy = signal.type === "buy";
  return (
    <div
      className={`flex items-center gap-3 rounded-lg px-3 py-2 text-xs ${
        isBuy ? "border-l-2 border-profit bg-profit/5" : "border-l-2 border-loss bg-loss/5"
      }`}
    >
      <Badge
        variant="outline"
        className={`h-5 text-[10px] ${
          isBuy ? "border-profit/30 text-profit" : "border-loss/30 text-loss"
        }`}
      >
        {isBuy ? "买" : "卖"}
      </Badge>
      <span className="font-num text-text-secondary">{signal.timestamp}</span>
      <span className="font-num text-text-primary">{formatCurrency(signal.price)}</span>
      {signal.confidence != null && (
        <span className="text-text-muted">置信 {signal.confidence}%</span>
      )}
      <span className="text-text-muted">{signal.reason}</span>
    </div>
  );
}
