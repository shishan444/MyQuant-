import { useLayoutEffect, useEffect, useRef, useMemo, useImperativeHandle, forwardRef } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  createSeriesMarkers,
} from "lightweight-charts";
import type {
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  Time,
  UTCTimestamp,
} from "lightweight-charts";

import { DARK_CHART_THEME, CHART_COLORS } from "./core/chartThemes";
import { useChartSync } from "./core/useChartSync";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CandleData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface IndicatorData {
  id: string;
  type: string;
  color: string;
  data: Array<{ time: string; value: number }>;
}

interface SignalData {
  type: "buy" | "sell";
  timestamp: string;
}

interface TriggerMarker {
  id: number;
  time: string;
  matched: boolean;
}

interface KlineChartProps {
  data: CandleData[];
  indicators?: IndicatorData[];
  signals?: SignalData[];
  triggers?: TriggerMarker[];
  height?: number;
  onTriggerClick?: (id: number) => void;
}

export interface KlineChartHandle {
  scrollToTime: (time: string) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert ISO timestamp to lightweight-charts compatible Time.
 *  For intraday data, returns UTCTimestamp (seconds since epoch).
 *  For daily data, returns "yyyy-mm-dd" string. */
function toTime(ts: string): Time {
  const date = new Date(ts);
  if (isNaN(date.getTime())) {
    return ts.slice(0, 10) as Time;
  }
  // Use UTCTimestamp for intraday, string for daily
  return Math.floor(date.getTime() / 1000) as UTCTimestamp;
}

/** Transform raw candle data into the format expected by CandlestickSeries. */
function toCandleData(data: CandleData[]) {
  return data.map((d) => ({
    time: toTime(d.timestamp),
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close,
  }));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const KlineChart = forwardRef<KlineChartHandle, KlineChartProps>(function KlineChart({
  data,
  indicators,
  signals,
  triggers,
  height = 450,
  onTriggerClick: _onTriggerClick,
}, ref) {
  const mainRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);

  const mainChartRef = useRef<IChartApi | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const indicatorSeriesRefs = useRef<Map<string, ISeriesApi<"Line">>>(
    new Map(),
  );
  const rsiSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  // Track RSI reference line series for cleanup
  const rsiRefLineSeriesRef = useRef<ISeriesApi<"Line">[]>([]);

  // Stable callbacks so effect dependencies stay clean.
  const memoizedCandles = useMemo(() => toCandleData(data), [data]);
  const memoizedIndicators = useMemo(() => indicators ?? [], [indicators]);
  const memoizedSignals = useMemo(() => signals ?? [], [signals]);
  const memoizedTriggers = useMemo(() => triggers ?? [], [triggers]);

  // Expose imperative handle for scrolling to a specific time
  useImperativeHandle(ref, () => ({
    scrollToTime: (time: string) => {
      const chart = mainChartRef.current;
      if (!chart) return;
      const ts = toTime(time);
      chart.timeScale().setVisibleRange({
        from: ts as UTCTimestamp,
        to: ts as UTCTimestamp,
      });
    },
  }), []);

  // Sync charts via shared hook.
  useChartSync(mainChartRef.current, rsiChartRef.current);

  // -------------------------------------------------------------------------
  // Chart creation / destruction (useLayoutEffect avoids flash)
  // -------------------------------------------------------------------------
  useLayoutEffect(() => {
    if (!mainRef.current || !rsiRef.current) return;

    const mainHeight = Math.round(height * 0.75);
    const subHeight = Math.round(height * 0.25);

    // -- Main chart (K-line) --
    const mainChart = createChart(mainRef.current, {
      ...DARK_CHART_THEME,
      width: mainRef.current.clientWidth,
      height: mainHeight,
    });

    const candleSeries = mainChart.addSeries(CandlestickSeries, {
      upColor: CHART_COLORS.candleUp,
      downColor: CHART_COLORS.candleDown,
      borderVisible: false,
      wickUpColor: CHART_COLORS.candleUp,
      wickDownColor: CHART_COLORS.candleDown,
    });

    mainChartRef.current = mainChart;
    candleSeriesRef.current = candleSeries;

    // -- RSI sub-chart --
    const rsiChart = createChart(rsiRef.current, {
      ...DARK_CHART_THEME,
      width: rsiRef.current.clientWidth,
      height: subHeight,
      timeScale: {
        ...DARK_CHART_THEME.timeScale,
        visible: false,
      },
    });

    const rsiSeries = rsiChart.addSeries(LineSeries, {
      color: CHART_COLORS.rsi,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    rsiChartRef.current = rsiChart;
    rsiSeriesRef.current = rsiSeries;

    // -- ResizeObserver --
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        if (entry.target === mainRef.current) {
          mainChart.applyOptions({ width });
        } else if (entry.target === rsiRef.current) {
          rsiChart.applyOptions({ width });
        }
      }
    });

    resizeObserver.observe(mainRef.current);
    resizeObserver.observe(rsiRef.current);

    return () => {
      resizeObserver.disconnect();
      mainChart.remove();
      rsiChart.remove();
      mainChartRef.current = null;
      rsiChartRef.current = null;
      candleSeriesRef.current = null;
      rsiSeriesRef.current = null;
      indicatorSeriesRefs.current.clear();
      markersPluginRef.current = null;
      rsiRefLineSeriesRef.current = [];
    };
  }, [height]);

  // -------------------------------------------------------------------------
  // Data updates (separate effect to avoid re-creating charts)
  // -------------------------------------------------------------------------
  useEffect(() => {
    const mainChart = mainChartRef.current;
    const candleSeries = candleSeriesRef.current;
    if (!mainChart || !candleSeries) return;

    // -- Candle data --
    candleSeries.setData(memoizedCandles);

    // -- Indicator lines --
    // Remove stale series
    for (const [id, series] of indicatorSeriesRefs.current) {
      const stillExists = memoizedIndicators.some((i) => i.id === id);
      if (!stillExists) {
        mainChart.removeSeries(series);
        indicatorSeriesRefs.current.delete(id);
      }
    }

    // Add / update indicator series
    for (const indicator of memoizedIndicators) {
      let series = indicatorSeriesRefs.current.get(indicator.id);
      if (!series) {
        series = mainChart.addSeries(LineSeries, {
          color: indicator.color,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: true,
        });
        indicatorSeriesRefs.current.set(indicator.id, series);
      }
      series.setData(
        indicator.data.map((d) => ({ time: toTime(d.time), value: d.value })),
      );
    }

    // -- Build markers from both signals and triggers --
    const markers: Array<{
      time: Time;
      position: "aboveBar" | "belowBar";
      color: string;
      shape: "arrowUp" | "arrowDown" | "circle";
      text: string;
    }> = [];

    // Signal markers (buy/sell)
    for (const s of memoizedSignals) {
      markers.push({
        time: toTime(s.timestamp),
        position: s.type === "buy" ? "belowBar" : "aboveBar",
        color: s.type === "buy" ? CHART_COLORS.buySignal : CHART_COLORS.sellSignal,
        shape: s.type === "buy" ? "arrowUp" : "arrowDown",
        text: s.type === "buy" ? "B" : "S",
      });
    }

    // Trigger markers
    for (const t of memoizedTriggers) {
      markers.push({
        time: toTime(t.time),
        position: "aboveBar",
        color: t.matched ? "#00C853" : "#EF4444",
        shape: "circle",
        text: `(${t.id})`,
      });
    }

    if (markersPluginRef.current) {
      markersPluginRef.current.setMarkers(markers);
    } else {
      markersPluginRef.current = createSeriesMarkers(candleSeries, markers);
    }

    // -- Fit content --
    mainChart.timeScale().fitContent();
  }, [memoizedCandles, memoizedIndicators, memoizedSignals, memoizedTriggers]);

  // -------------------------------------------------------------------------
  // RSI data update
  // -------------------------------------------------------------------------
  const rsiIndicator = memoizedIndicators.find((i) => i.type === "rsi");
  const rsiData = useMemo(
    () =>
      rsiIndicator
        ? rsiIndicator.data.map((d) => ({
            time: toTime(d.time),
            value: d.value,
          }))
        : [],
    [rsiIndicator],
  );

  useEffect(() => {
    const rsiSeries = rsiSeriesRef.current;
    const rsiChart = rsiChartRef.current;
    if (!rsiSeries || !rsiChart) return;

    rsiSeries.setData(rsiData);

    // Remove previous reference lines
    for (const s of rsiRefLineSeriesRef.current) {
      rsiChart.removeSeries(s);
    }
    rsiRefLineSeriesRef.current = [];

    // Draw overbought / oversold horizontal reference lines when data exists
    if (rsiData.length > 0) {
      const time = rsiData[0].time;
      const lastTime = rsiData[rsiData.length - 1].time;

      const refLines: ISeriesApi<"Line">[] = [];

      // Overbought line at 70
      const obSeries = rsiChart.addSeries(LineSeries, {
        color: CHART_COLORS.overbought,
        lineWidth: 1,
        lineStyle: 2, // Dashed
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      obSeries.setData([
        { time, value: 70 },
        { time: lastTime, value: 70 },
      ]);
      refLines.push(obSeries);

      // Oversold line at 30
      const osSeries = rsiChart.addSeries(LineSeries, {
        color: CHART_COLORS.oversold,
        lineWidth: 1,
        lineStyle: 2, // Dashed
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      osSeries.setData([
        { time, value: 30 },
        { time: lastTime, value: 30 },
      ]);
      refLines.push(osSeries);

      rsiRefLineSeriesRef.current = refLines;
      rsiChart.timeScale().fitContent();
    }
  }, [rsiData]);

  return (
    <div className="flex flex-col" style={{ height }}>
      <div ref={mainRef} className="flex-[3] min-h-0" />
      <div
        ref={rsiRef}
        className="flex-1 min-h-0 border-t border-slate-800/50"
      />
    </div>
  );
});

export { KlineChart };
export type { KlineChartProps, CandleData, IndicatorData, SignalData, TriggerMarker };
