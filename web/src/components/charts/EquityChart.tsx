import ReactECharts from 'echarts-for-react';
import type { EquityPoint } from '@/types';

interface EquityChartProps {
  equityCurve: EquityPoint[];
}

export function EquityChart({ equityCurve }: EquityChartProps) {
  const times = equityCurve.map((p) => p.time);
  const strategyValues = equityCurve.map((p) => p.equity);
  const benchmarkValues = equityCurve.map((p) => p.benchmark);

  const option = {
    backgroundColor: '#161B22',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: '#21262D',
      borderColor: '#30363D',
      textStyle: { color: '#E6EDF3', fontSize: 12 },
    },
    legend: {
      data: ['Strategy', 'BTC Buy & Hold'],
      top: 0,
      textStyle: { color: '#8B949E', fontSize: 11 },
      itemWidth: 16,
      itemHeight: 8,
    },
    grid: {
      left: 50,
      right: 20,
      top: 35,
      bottom: 30,
    },
    xAxis: {
      type: 'category' as const,
      data: times,
      axisLine: { lineStyle: { color: '#30363D' } },
      axisLabel: { color: '#8B949E', fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value' as const,
      axisLine: { lineStyle: { color: '#30363D' } },
      axisLabel: { color: '#8B949E', fontSize: 10 },
      splitLine: { lineStyle: { color: '#21262D' } },
    },
    series: [
      {
        name: 'Strategy',
        type: 'line',
        data: strategyValues,
        smooth: true,
        lineStyle: { color: '#1E88E5', width: 2 },
        itemStyle: { color: '#1E88E5' },
        showSymbol: false,
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(30, 136, 229, 0.25)' },
              { offset: 1, color: 'rgba(30, 136, 229, 0.02)' },
            ],
          },
        },
      },
      {
        name: 'BTC Buy & Hold',
        type: 'line',
        data: benchmarkValues,
        smooth: true,
        lineStyle: { color: '#7C4DFF', width: 2, type: 'dashed' as const },
        itemStyle: { color: '#7C4DFF' },
        showSymbol: false,
      },
    ],
  };

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-[var(--border)]">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">Equity Curve</h3>
      </div>
      <ReactECharts option={option} style={{ height: 300 }} />
    </div>
  );
}
