import ReactECharts from 'echarts-for-react';
import type { GenerationHistoryPoint } from '@/types';

interface GenerationChartProps {
  data: GenerationHistoryPoint[];
  targetScore: number;
}

export function GenerationChart({ data, targetScore }: GenerationChartProps) {
  const generations = data.map((d) => d.generation);
  const bestScores = data.map((d) => d.best_score);
  const avgScores = data.map((d) => d.avg_score);
  const targetLine = data.map(() => targetScore);

  const option = {
    backgroundColor: '#161B22',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: '#21262D',
      borderColor: '#30363D',
      textStyle: { color: '#E6EDF3', fontSize: 12 },
    },
    legend: {
      data: ['Best Score', 'Avg Score', 'Target'],
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
      data: generations,
      name: 'Generation',
      nameTextStyle: { color: '#8B949E', fontSize: 10 },
      axisLine: { lineStyle: { color: '#30363D' } },
      axisLabel: { color: '#8B949E', fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value' as const,
      name: 'Score',
      nameTextStyle: { color: '#8B949E', fontSize: 10 },
      axisLine: { lineStyle: { color: '#30363D' } },
      axisLabel: { color: '#8B949E', fontSize: 10 },
      splitLine: { lineStyle: { color: '#21262D' } },
    },
    series: [
      {
        name: 'Best Score',
        type: 'line',
        data: bestScores,
        smooth: true,
        lineStyle: { color: '#00C853', width: 2 },
        itemStyle: { color: '#00C853' },
        showSymbol: data.length < 30,
        symbolSize: 4,
        areaStyle: {
          color: {
            type: 'linear' as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 200, 83, 0.15)' },
              { offset: 1, color: 'rgba(0, 200, 83, 0.01)' },
            ],
          },
        },
      },
      {
        name: 'Avg Score',
        type: 'line',
        data: avgScores,
        smooth: true,
        lineStyle: { color: '#2196F3', width: 1.5 },
        itemStyle: { color: '#2196F3' },
        showSymbol: false,
      },
      {
        name: 'Target',
        type: 'line',
        data: targetLine,
        lineStyle: { color: '#FFD600', width: 1, type: 'dashed' as const },
        itemStyle: { color: '#FFD600' },
        showSymbol: false,
      },
    ],
  };

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden">
      <div className="px-3 py-2 border-b border-[var(--border)]">
        <h3 className="text-sm font-medium text-[var(--text-primary)]">Score Trend by Generation</h3>
      </div>
      <ReactECharts option={option} style={{ height: 280 }} />
    </div>
  );
}
