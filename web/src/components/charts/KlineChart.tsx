import { useLayoutEffect, useEffect, useRef, useMemo, useImperativeHandle, forwardRef, useState, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  createSeriesMarkers,
} from "lightweight-charts";
import type {
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  Time,
  UTCTimestamp,
  MouseEventParams,
} from "lightweight-charts";

import { DARK_CHART_THEME, CHART_COLORS } from "./core/chartThemes";
import { useChartSync } from "./core/useChartSync";
import { ChartEmbeddedLegend } from "./ChartEmbeddedLegend";
import { ChartToolbar } from "./ChartToolbar";
import { useChartSettings } from "@/stores/chart-settings";
import type { BollingerBandData, MTFIndicatorData, LegendGroup, LegendItem } from "@/types/chart";

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
  bollData?: BollingerBandData;
  volumeData?: Array<{ time: string; value: number; color?: string }>;
  mtfIndicators?: MTFIndicatorData[];
}

export interface KlineChartHandle {
  scrollToTime: (time: string) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  resetView: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toTime(ts: string): Time {
  const withT = ts.includes("T") ? ts : ts.replace(" ", "T");
  const date = new Date(withT);
  if (isNaN(date.getTime())) {
    return ts.slice(0, 10) as Time;
  }
  return Math.floor(date.getTime() / 1000) as UTCTimestamp;
}

function toCandleData(data: CandleData[]) {
  const mapped = data.map((d) => ({
    time: toTime(d.timestamp),
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close,
  }));
  return mapped
    .filter((d) => typeof d.time === "number" && !isNaN(d.time as number))
    .sort((a, b) => (a.time as number) - (b.time as number));
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
  bollData,
  volumeData,
  mtfIndicators,
}, ref) {
  const mainRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const mainChartRef = useRef<IChartApi | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const indicatorSeriesRefs = useRef<Map<string, ISeriesApi<"Line">>>(
    new Map(),
  );
  const rsiSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const rsiRefLineSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const bollSeriesRefs = useRef<ISeriesApi<"Line">[]>([]);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const mtfSeriesRefs = useRef<ISeriesApi<"Line">[]>([]);

  // Legend state
  const [legendGroups, setLegendGroups] = useState<LegendGroup[]>([]);
  const [legendValues, setLegendValues] = useState<Record<string, string>>({});

  // Chart settings from store
  const chartSettings = useChartSettings();

  // Fullscreen state
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Stable callbacks so effect dependencies stay clean.
  const memoizedCandles = useMemo(() => toCandleData(data), [data]);
  const memoizedIndicators = useMemo(() => indicators ?? [], [indicators]);
  const memoizedSignals = useMemo(() => signals ?? [], [signals]);
  const memoizedTriggers = useMemo(() => triggers ?? [], [triggers]);
  const memoizedBollData = useMemo(() => bollData, [bollData]);
  const memoizedVolumeData = useMemo(() => volumeData, [volumeData]);
  const memoizedMtfIndicators = useMemo(() => mtfIndicators ?? [], [mtfIndicators]);

  // Expose imperative handle
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
    zoomIn: () => {
      const chart = mainChartRef.current;
      if (!chart) return;
      const range = chart.timeScale().getVisibleLogicalRange();
      if (range) {
        const barCount = range.to - range.from;
        const center = (range.from + range.to) / 2;
        const newBarCount = barCount * 0.8;
        chart.timeScale().setVisibleLogicalRange({
          from: Math.round(center - newBarCount / 2),
          to: Math.round(center + newBarCount / 2),
        });
      }
    },
    zoomOut: () => {
      const chart = mainChartRef.current;
      if (!chart) return;
      const range = chart.timeScale().getVisibleLogicalRange();
      if (range) {
        const barCount = range.to - range.from;
        const center = (range.from + range.to) / 2;
        const newBarCount = barCount * 1.25;
        chart.timeScale().setVisibleLogicalRange({
          from: Math.round(center - newBarCount / 2),
          to: Math.round(center + newBarCount / 2),
        });
      }
    },
    resetView: () => {
      mainChartRef.current?.timeScale().fitContent();
    },
  }), []);

  // Sync charts via shared hook.
  useChartSync(mainChartRef.current, rsiChartRef.current);

  // Build legend groups from current data
  useEffect(() => {
    const groups: LegendGroup[] = [];

    // OHLCV group
    groups.push({
      id: "ohlcv",
      label: "OHLCV",
      items: [
        { id: "candle", label: "K线", color: "#94a3b8", visible: true },
      ],
    });

    // EMA group from store
    const emaItems: LegendItem[] = chartSettings.emaList
      .filter((e) => e.enabled)
      .map((e) => ({
        id: `ema_${e.period}`,
        label: `EMA(${e.period})`,
        color: e.color,
        visible: true,
      }));
    if (emaItems.length > 0) {
      groups.push({ id: "ema", label: "趋势", items: emaItems });
    }

    // BOLL group
    if (memoizedBollData && chartSettings.boll.enabled) {
      groups.push({
        id: "boll",
        label: "BOLL",
        items: [
          { id: "boll_upper", label: "上轨", color: "#F59E0B", visible: true },
          { id: "boll_middle", label: "中轨", color: "#F59E0B88", visible: true },
          { id: "boll_lower", label: "下轨", color: "#F59E0B", visible: true },
        ],
      });
    }

    // MTF group
    if (memoizedMtfIndicators.length > 0) {
      groups.push({
        id: "mtf",
        label: "跨周期",
        items: memoizedMtfIndicators.map((m) => ({
          id: `mtf_${m.sourceTimeframe}_${m.indicatorName}`,
          label: `${m.sourceTimeframe.toUpperCase()} ${m.indicatorName}`,
          color: m.color,
          visible: true,
        })),
      });
    }

    // Triggers group
    if (memoizedTriggers.length > 0) {
      groups.push({
        id: "triggers",
        label: "触发点",
        items: [
          { id: "trigger_markers", label: `触发 (${memoizedTriggers.length})`, color: "#00C853", visible: true },
        ],
      });
    }

    setLegendGroups(groups);
  }, [chartSettings.emaList, chartSettings.boll.enabled, memoizedBollData, memoizedMtfIndicators, memoizedTriggers]);

  const handleLegendToggle = useCallback((groupId: string, itemId: string) => {
    // Toggle visibility by applying transparent color to hidden series
    const seriesMap = indicatorSeriesRefs.current;
    const bollSeries = bollSeriesRefs.current;
    const mtfSeries = mtfSeriesRefs.current;

    // Try to find the series in various ref maps
    const targetSeries =
      seriesMap.get(itemId) ??
      (groupId === "boll" ? bollSeries[["boll_upper", "boll_middle", "boll_lower"].indexOf(itemId)] : null) ??
      (groupId === "mtf" ? mtfSeries.find((s) => s.options().title === itemId) : null);

    if (targetSeries) {
      const currentColor = targetSeries.options().color as string;
      if (currentColor === "transparent") {
        // Restore: we need to know the original color, simplified approach
        targetSeries.applyOptions({ color: "#F59E0B" });
      } else {
        targetSeries.applyOptions({ color: "transparent" });
      }
    }
  }, []);

  // -------------------------------------------------------------------------
  // Chart creation / destruction
  // -------------------------------------------------------------------------
  useLayoutEffect(() => {
    if (!mainRef.current || !rsiRef.current) return;

    const mainHeight = Math.round(height * 0.78);
    const subHeight = Math.round(height * 0.22);

    // -- Main chart --
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

    // Crosshair move for legend values
    mainChart.subscribeCrosshairMove((param: MouseEventParams) => {
      if (!param.time || !param.seriesData) {
        return;
      }
      const vals: Record<string, string> = {};
      const candleData = param.seriesData.get(candleSeries);
      if (candleData && "close" in candleData) {
        vals["candle"] = `C: ${(candleData as { close: number }).close.toFixed(2)}`;
      }
      // Update indicator values
      for (const [id, series] of indicatorSeriesRefs.current) {
        const sd = param.seriesData.get(series);
        if (sd && "value" in sd) {
          vals[id] = (sd as { value: number }).value.toFixed(2);
        }
      }
      setLegendValues(vals);
    });

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
      bollSeriesRefs.current = [];
      volumeSeriesRef.current = null;
      mtfSeriesRefs.current = [];
    };
  }, [height]);

  // -------------------------------------------------------------------------
  // Data updates
  // -------------------------------------------------------------------------
  useEffect(() => {
    const mainChart = mainChartRef.current;
    const candleSeries = candleSeriesRef.current;
    if (!mainChart || !candleSeries) return;

    // -- Candle data --
    candleSeries.setData(memoizedCandles);

    // -- Remove stale indicator series --
    for (const [id, series] of indicatorSeriesRefs.current) {
      const stillExists = memoizedIndicators.some((i) => i.id === id);
      if (!stillExists) {
        mainChart.removeSeries(series);
        indicatorSeriesRefs.current.delete(id);
      }
    }

    // -- Indicator lines --
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

    // -- EMA lines from chart settings --
    const emaList = chartSettings.emaList.filter((e) => e.enabled);
    // Remove old EMA series
    for (const [id, series] of indicatorSeriesRefs.current) {
      if (id.startsWith("ema_") && !emaList.some((e) => `ema_${e.period}` === id)) {
        mainChart.removeSeries(series);
        indicatorSeriesRefs.current.delete(id);
      }
    }
    // EMA data comes from the indicators prop (computed by backend), so we don't create new series here
    // The EMA series are handled through the indicators prop

    // -- BOLL bands --
    for (const s of bollSeriesRefs.current) {
      mainChart.removeSeries(s);
    }
    bollSeriesRefs.current = [];

    if (memoizedBollData && chartSettings.boll.enabled) {
      const bollColor = chartSettings.boll.color || "#F59E0B";

      const upperSeries = mainChart.addSeries(LineSeries, {
        color: bollColor,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "boll_upper",
      });
      upperSeries.setData(memoizedBollData.upper.map((d) => ({ time: toTime(d.time), value: d.value })));

      const middleSeries = mainChart.addSeries(LineSeries, {
        color: `${bollColor}88`,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "boll_middle",
      });
      middleSeries.setData(memoizedBollData.middle.map((d) => ({ time: toTime(d.time), value: d.value })));

      const lowerSeries = mainChart.addSeries(LineSeries, {
        color: bollColor,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "boll_lower",
      });
      lowerSeries.setData(memoizedBollData.lower.map((d) => ({ time: toTime(d.time), value: d.value })));

      bollSeriesRefs.current = [upperSeries, middleSeries, lowerSeries];
    }

    // -- Volume --
    if (volumeSeriesRef.current) {
      mainChart.removeSeries(volumeSeriesRef.current);
      volumeSeriesRef.current = null;
    }

    if (memoizedVolumeData && memoizedVolumeData.length > 0) {
      const volSeries = mainChart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "vol",
      });
      mainChart.priceScale("vol").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volSeries.setData(
        memoizedVolumeData.map((d) => ({
          time: toTime(d.time),
          value: d.value,
          color: d.color ?? "rgba(100,116,139,0.3)",
        })),
      );
      volumeSeriesRef.current = volSeries;
    }

    // -- MTF indicators --
    for (const s of mtfSeriesRefs.current) {
      mainChart.removeSeries(s);
    }
    mtfSeriesRefs.current = [];

    if (memoizedMtfIndicators.length > 0) {
      for (const mtf of memoizedMtfIndicators) {
        const mtfSeries = mainChart.addSeries(LineSeries, {
          color: mtf.color,
          lineWidth: 1,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          title: `mtf_${mtf.sourceTimeframe}_${mtf.indicatorName}`,
        });
        mtfSeries.setData(
          mtf.data.map((d) => ({ time: toTime(d.time), value: d.value })),
        );
        mtfSeriesRefs.current.push(mtfSeries);
      }
    }

    // -- Build markers --
    const markers: Array<{
      time: Time;
      position: "aboveBar" | "belowBar";
      color: string;
      shape: "arrowUp" | "arrowDown" | "circle";
      text: string;
    }> = [];

    for (const s of memoizedSignals) {
      markers.push({
        time: toTime(s.timestamp),
        position: s.type === "buy" ? "belowBar" : "aboveBar",
        color: s.type === "buy" ? CHART_COLORS.buySignal : CHART_COLORS.sellSignal,
        shape: s.type === "buy" ? "arrowUp" : "arrowDown",
        text: s.type === "buy" ? "B" : "S",
      });
    }

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

    mainChart.timeScale().fitContent();
  }, [memoizedCandles, memoizedIndicators, memoizedSignals, memoizedTriggers, memoizedBollData, memoizedVolumeData, memoizedMtfIndicators, chartSettings.boll]);

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

    for (const s of rsiRefLineSeriesRef.current) {
      rsiChart.removeSeries(s);
    }
    rsiRefLineSeriesRef.current = [];

    if (rsiData.length > 0) {
      const time = rsiData[0].time;
      const lastTime = rsiData[rsiData.length - 1].time;

      const refLines: ISeriesApi<"Line">[] = [];

      const obSeries = rsiChart.addSeries(LineSeries, {
        color: CHART_COLORS.overbought,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      obSeries.setData([
        { time, value: 70 },
        { time: lastTime, value: 70 },
      ]);
      refLines.push(obSeries);

      const osSeries = rsiChart.addSeries(LineSeries, {
        color: CHART_COLORS.oversold,
        lineWidth: 1,
        lineStyle: 2,
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

  // Fullscreen toggle
  const handleFullscreen = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
    }
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative"
      style={{ height: isFullscreen ? "100vh" : height }}
    >
      {/* Toolbar */}
      <div className="absolute right-2 top-2 z-20">
        <ChartToolbar
          onZoomIn={() => {
            const chart = mainChartRef.current;
            if (!chart) return;
            const range = chart.timeScale().getVisibleLogicalRange();
            if (range) {
              const barCount = range.to - range.from;
              const center = (range.from + range.to) / 2;
              const newBarCount = barCount * 0.8;
              chart.timeScale().setVisibleLogicalRange({
                from: Math.round(center - newBarCount / 2),
                to: Math.round(center + newBarCount / 2),
              });
            }
          }}
          onZoomOut={() => {
            const chart = mainChartRef.current;
            if (!chart) return;
            const range = chart.timeScale().getVisibleLogicalRange();
            if (range) {
              const barCount = range.to - range.from;
              const center = (range.from + range.to) / 2;
              const newBarCount = barCount * 1.25;
              chart.timeScale().setVisibleLogicalRange({
                from: Math.round(center - newBarCount / 2),
                to: Math.round(center + newBarCount / 2),
              });
            }
          }}
          onReset={() => mainChartRef.current?.timeScale().fitContent()}
          onFullscreen={handleFullscreen}
        />
      </div>

      {/* Legend */}
      <ChartEmbeddedLegend
        groups={legendGroups}
        onToggle={handleLegendToggle}
        values={legendValues}
      />

      <div className="flex flex-col h-full">
        <div ref={mainRef} className="flex-[3] min-h-0" />
        <div
          ref={rsiRef}
          className="flex-1 min-h-0 border-t border-slate-800/50"
        />
      </div>
    </div>
  );
});

export { KlineChart };
export type { KlineChartProps, CandleData, IndicatorData, SignalData, TriggerMarker };
