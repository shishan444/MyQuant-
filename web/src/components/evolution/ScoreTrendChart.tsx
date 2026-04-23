import { useMemo } from "react";
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ComposedChart,
} from "recharts";
import type { EvolutionHistoryRecord } from "@/types/api";
import {
  transformChartData,
  type ChartDataPoint,
  type ChartTransformResult,
} from "@/utils/evolutionChart";

interface ScoreTrendChartProps {
  records: EvolutionHistoryRecord[];
  targetScore: number;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string; dataKey: string }>;
  label?: number;
}) {
  if (!active || !payload) return null;
  const dataPoint = payload[0]?.payload as ChartDataPoint | undefined;
  if (!dataPoint) return null;

  const delta = dataPoint.prevBestScore != null
    ? dataPoint.bestScore - dataPoint.prevBestScore
    : undefined;
  const diversityPct = dataPoint.diversity != null
    ? `${(dataPoint.diversity * 100).toFixed(0)}%`
    : null;

  return (
    <div className="rounded-lg border border-slate-700/50 bg-[#0d1117]/95 px-3 py-2 text-xs min-w-[160px]">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="font-medium text-slate-300">第 {label} 代</span>
        {dataPoint.population > 1 && (
          <span className="text-slate-500">P{dataPoint.population}</span>
        )}
      </div>

      {/* Best score with delta */}
      <p className="text-amber-400">
        最优分数: {dataPoint.bestScore.toFixed(1)}
        {delta != null && delta !== 0 && (
          <span className={delta > 0 ? "text-emerald-400 ml-1" : "text-red-400/70 ml-1"}>
            {delta > 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1)}
          </span>
        )}
      </p>

      {/* Cumulative best */}
      {dataPoint.cumulativeBest !== dataPoint.bestScore && (
        <p className="text-emerald-500/70">
          累计最佳: {dataPoint.cumulativeBest.toFixed(1)}
        </p>
      )}

      {/* Avg score */}
      <p className="text-purple-400/70">
        平均分数: {dataPoint.avgScore.toFixed(1)}
      </p>

      {/* Avg trades */}
      {dataPoint.avgTrades != null && (
        <p className="text-slate-400">
          种群平均交易: {dataPoint.avgTrades}
        </p>
      )}

      {/* Diversity */}
      {diversityPct != null && (
        <p className={
          dataPoint.diversity! > 0.7
            ? "text-emerald-400/80"
            : dataPoint.diversity! > 0.4
              ? "text-amber-400/80"
              : "text-red-400/70"
        }>
          种群多样性: {diversityPct}
        </p>
      )}

      {/* Stagnation (within current population) */}
      {dataPoint.stagnationCount > 0 && (
        <p className="text-orange-400/70">
          停滞: {dataPoint.stagnationCount} 代未突破
        </p>
      )}

      {/* Population boundary indicator */}
      {dataPoint.isPopulationBoundary && (
        <p className="mt-1 border-t border-slate-700/30 pt-1 text-cyan-400/80 font-medium">
          新种群开始
        </p>
      )}

      {/* Breakthrough indicator */}
      {dataPoint.isChampionChange && !dataPoint.isPopulationBoundary && (
        <p className="mt-1 border-t border-slate-700/30 pt-1 text-emerald-400 font-medium">
          最优记录刷新
        </p>
      )}
    </div>
  );
}

export function ScoreTrendChart({
  records,
  targetScore,
}: ScoreTrendChartProps) {
  const { data, championChanges, boundaries, stats }: ChartTransformResult = useMemo(
    () => transformChartData(records),
    [records],
  );

  if (data.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center">
        <span className="text-xs text-slate-600">暂无趋势数据</span>
      </div>
    );
  }

  const lastRecord = data[data.length - 1];

  // Compute Y-axis domain to include targetScore
  const allY = data.flatMap((d) => [d.bestScore, d.avgScore]);
  const dataMin = Math.min(...allY);
  const dataMax = Math.max(...allY);
  const yMin = Math.floor(Math.min(dataMin, targetScore) / 5) * 5 - 5;
  const yMax = Math.ceil(Math.max(dataMax, targetScore) / 5) * 5 + 5;

  return (
    <div>
      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(100,116,139,0.15)"
            />
            <XAxis
              dataKey="generation"
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={{ stroke: "rgba(100,116,139,0.2)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={{ stroke: "rgba(100,116,139,0.2)" }}
              tickLine={false}
              domain={[yMin, yMax]}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              y={targetScore}
              stroke="#94a3b8"
              strokeDasharray="6 3"
              strokeWidth={1}
              label={{
                value: `目标 ${targetScore}`,
                position: "right",
                fill: "#94a3b8",
                fontSize: 10,
              }}
            />
            {/* Population boundary vertical lines */}
            {boundaries.map((gen) => (
              <ReferenceLine
                key={`boundary-${gen}`}
                x={gen}
                stroke="rgba(6,182,212,0.25)"
                strokeDasharray="4 4"
                strokeWidth={1}
              />
            ))}
            {/* Per-generation best score (can drop at population boundaries) */}
            <Line
              type="monotone"
              dataKey="bestScore"
              stroke="#eab308"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#eab308" }}
              name="bestScore"
            />
            {/* Cumulative best (never decreases) */}
            <Line
              type="monotone"
              dataKey="cumulativeBest"
              stroke="rgba(34,197,94,0.5)"
              strokeWidth={1}
              strokeDasharray="2 3"
              dot={false}
              name="cumulativeBest"
            />
            <Line
              type="monotone"
              dataKey="avgScore"
              stroke="rgba(168,85,247,0.4)"
              strokeWidth={1}
              strokeDasharray="4 2"
              dot={false}
              activeDot={{ r: 3, fill: "rgba(168,85,247,0.4)" }}
              name="avgScore"
            />
            {/* Champion change markers */}
            <Scatter
              data={championChanges}
              dataKey="bestScore"
              name="championMarker"
              fill="#22c55e"
              shape="diamond"
              r={4}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {/* Legend */}
      <div className="mt-1 flex items-center justify-center gap-4 text-[10px] text-slate-600">
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 bg-amber-400" />
          最优分数
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 border-t border-dashed border-emerald-400/50" />
          累计最佳
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 border-t border-dashed border-purple-400/40" />
          平均分数
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 border-t border-dashed border-slate-400" />
          目标线
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rotate-45 bg-emerald-500" />
          最优更新
        </span>
      </div>
      {/* Summary stats */}
      <div className="mt-2 flex items-center justify-center gap-4 text-[10px]">
        <span className="text-slate-500">
          最优刷新 {stats.totalChampionChanges} 次
        </span>
        <span className={stats.maxStagnation > 10 ? "text-orange-400" : "text-slate-500"}>
          最长停滞 {stats.maxStagnation} 代
        </span>
        {lastRecord?.diversity != null && typeof lastRecord.diversity === "number" && (
          <span className={
            lastRecord.diversity > 0.7
              ? "text-emerald-400/70"
              : lastRecord.diversity > 0.4
                ? "text-amber-400/70"
                : "text-red-400/70"
          }>
            当前多样性 {(lastRecord.diversity * 100).toFixed(0)}%
          </span>
        )}
        {stats.populationCount > 1 && (
          <span className="text-cyan-400/70">
            {stats.populationCount} 个种群
          </span>
        )}
      </div>
    </div>
  );
}
