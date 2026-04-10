import { useEffect, useRef } from 'react';
import {
  createChart,
  CandlestickSeries,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
} from 'lightweight-charts';
import type { BacktestTrade } from '@/types';

interface KlineChartProps {
  candles: Array<{
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
  }>;
  trades: BacktestTrade[];
}

export function KlineChart({ candles, trades }: KlineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;

    const chart = createChart(container, {
      layout: {
        background: { color: '#161B22' },
        textColor: '#8B949E',
      },
      grid: {
        vertLines: { color: '#21262D' },
        horzLines: { color: '#21262D' },
      },
      rightPriceScale: {
        borderColor: '#30363D',
      },
      timeScale: {
        borderColor: '#30363D',
        timeVisible: true,
      },
      crosshair: {
        vertLine: { color: '#484F58' },
        horzLine: { color: '#484F58' },
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#00C853',
      downColor: '#FF1744',
      wickUpColor: '#00C853',
      wickDownColor: '#FF1744',
      borderVisible: false,
    });

    const markersPlugin = createSeriesMarkers(series, []);

    chartRef.current = chart;
    seriesRef.current = series;
    markersRef.current = markersPlugin;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.resize(width, height);
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !markersRef.current || candles.length === 0) return;

    const series = seriesRef.current;
    const markersPlugin = markersRef.current;

    series.setData(
      candles.map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );

    const markers = trades.flatMap((trade) => [
      {
        time: trade.entry_time as Time,
        position: 'belowBar' as const,
        shape: 'arrowUp' as const,
        color: '#00C853',
        text: `B ${trade.entry_price.toFixed(0)}`,
      },
      {
        time: trade.exit_time as Time,
        position: 'aboveBar' as const,
        shape: 'arrowDown' as const,
        color: '#FF1744',
        text: `S ${trade.exit_price.toFixed(0)}`,
      },
    ]);

    markersPlugin.setMarkers(markers);
    chartRef.current?.timeScale().fitContent();
  }, [candles, trades]);

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-[var(--border)]">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">K-Line Chart</h3>
      </div>
      <div ref={containerRef} className="w-full" style={{ height: 400 }} />
    </div>
  );
}
