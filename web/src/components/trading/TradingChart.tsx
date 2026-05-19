import { useMemo, useState } from "react";
import { KlineChart } from "@/components/charts/KlineChart";
import { useChartIndicators, type SubChartType } from "@/hooks/useChartIndicators";
import type { PaperTrade } from "@/services/trading";
import type { SignalData } from "@/components/charts/KlineChart";

interface TradingChartProps {
  symbol: string;
  timeframe: string;
  trades: PaperTrade[];
  height?: number;
  isActive?: boolean;
}

/** timeframe string -> minutes */
const TF_MINUTES: Record<string, number> = {
  "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
  "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
  "1d": 1440, "3d": 4320, "1w": 10080,
};

const SUB_CHART_OPTIONS: { value: SubChartType; label: string }[] = [
  { value: "volume", label: "VOL" },
  { value: "macd", label: "MACD" },
  { value: "rsi", label: "RSI" },
  { value: "kdj", label: "KDJ" },
];

/** Calculate start date for the last N bars based on timeframe. */
function barsAgoDate(timeframe: string, bars: number): string {
  const minutes = (TF_MINUTES[timeframe] ?? 240) * bars;
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

function tradesToSignals(trades: PaperTrade[]): SignalData[] {
  return trades
    .filter((t) => t.side) // skip records with empty side
    .map((t) => ({
      type: `${t.action}_${t.side}` as SignalData["type"],
      timestamp: t.bar_time,
    }));
}

export function TradingChart({ symbol, timeframe, trades, height = 420, isActive }: TradingChartProps) {
  const [subChartType, setSubChartType] = useState<SubChartType>("volume");

  // Only load the last 200 bars of data for paper trading chart
  const dateRange = useMemo(() => ({ start: barsAgoDate(timeframe, 200) }), [timeframe]);

  const {
    candleData,
    volumeData,
    chartIndicators,
    chartBollData,
    macdData,
    kdjData,
    isLoadingOhlcv,
  } = useChartIndicators({
    symbol,
    timeframe,
    dateRange,
    subChartType,
    refetchInterval: isActive ? 30_000 : false,
  });

  const signals = useMemo(() => tradesToSignals(trades), [trades]);

  if (isLoadingOhlcv || !candleData?.length) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-border-default"
        style={{ height }}>
        <span className="text-sm text-text-muted">Loading chart...</span>
      </div>
    );
  }

  return (
    <div>
      {/* Sub-chart indicator selector */}
      <div className="flex items-center gap-0.5 mb-1">
        <span className="mr-1 text-[11px] text-slate-500">Sub-chart</span>
        {SUB_CHART_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setSubChartType(opt.value)}
            className={`rounded px-1.5 py-0.5 text-[11px] transition-colors ${
              subChartType === opt.value
                ? "bg-sky-400/20 text-sky-400"
                : "bg-slate-800/30 text-slate-500 hover:text-slate-400"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <KlineChart
        data={candleData}
        signals={signals}
        indicators={chartIndicators}
        bollData={chartBollData}
        macdData={macdData}
        kdjData={kdjData}
        volumeData={volumeData}
        subChartType={subChartType}
        height={height}
      />
    </div>
  );
}
