import { useMemo } from "react";
import {
  LineChart,
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

interface ScoreTrendChartProps {
  records: EvolutionHistoryRecord[];
  targetScore: number;
}

interface ChartDataPoint {
  generation: number;
  bestScore: number;
  avgScore: number;
  isChampionChange?: boolean;
  stagnationCount?: number;
  fallbackPct?: number;
  zeroTradePct?: number;
  avgTrades?: number;
}

function parseDiagnostics(top3Summary?: string): {
  fallbackPct?: number;
  zeroTradePct?: number;
  avgTrades?: number;
} {
  if (!top3Summary) return {};
  try {
    const match = top3Summary.match(/diag=(\{.*\})/);
    if (match) {
      return JSON.parse(match[1]);
    }
  } catch {
    // ignore parse errors
  }
  return {};
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
  return (
    <div className="rounded-lg border border-slate-700/50 bg-[#0d1117]/95 px-3 py-2 text-xs">
      <p className="mb-1 font-medium text-slate-300">第 {label} 代</p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color }}>
          {entry.name === "bestScore"
            ? "最优分数"
            : entry.name === "avgScore"
              ? "平均分数"
              : entry.dataKey === "championMarker"
                ? "最优刷新"
                : entry.name}:{" "}
          {typeof entry.value === "number" ? entry.value.toFixed(1) : entry.value}
        </p>
      ))}
      {dataPoint && (
        <div className="mt-1 border-t border-slate-700/30 pt-1">
          {dataPoint.stagnationCount != null && dataPoint.stagnationCount > 0 && (
            <p className="text-orange-400/70">
              停滞: {dataPoint.stagnationCount} 代
            </p>
          )}
          {dataPoint.avgTrades != null && (
            <p className="text-slate-500">
              平均交易: {dataPoint.avgTrades}
            </p>
          )}
          {dataPoint.fallbackPct != null && dataPoint.fallbackPct > 0 && (
            <p className="text-red-400/70">
              Fallback: {dataPoint.fallbackPct}%
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function ScoreTrendChart({
  records,
  targetScore,
}: ScoreTrendChartProps) {
  const { data, championChanges } = useMemo(() => {
    const chartData: ChartDataPoint[] = records.map((r) => {
      const diag = parseDiagnostics(r.top3_summary);
      return {
        generation: r.generation,
        bestScore: r.best_score,
        avgScore: r.avg_score,
        ...diag,
      };
    });

    // Detect champion changes (score improvements)
    let prevBest = -Infinity;
    const changes: ChartDataPoint[] = [];
    for (const point of chartData) {
      if (point.bestScore > prevBest) {
        point.isChampionChange = true;
        changes.push(point);
      }
      prevBest = point.bestScore;
    }

    // Calculate stagnation count for each point
    let stagnationCounter = 0;
    let runningBest = -Infinity;
    for (const point of chartData) {
      if (point.bestScore > runningBest) {
        stagnationCounter = 0;
        runningBest = point.bestScore;
      } else {
        stagnationCounter++;
      }
      point.stagnationCount = stagnationCounter;
    }

    return { data: chartData, championChanges: changes };
  }, [records]);

  if (data.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center">
        <span className="text-xs text-slate-600">暂无趋势数据</span>
      </div>
    );
  }

  // Compute summary stats
  const maxStagnation = Math.max(...data.map((d) => d.stagnationCount ?? 0));
  const lastRecord = data[data.length - 1];
  const totalChampionChanges = championChanges.length;

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
              domain={["auto", "auto"]}
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
            <Line
              type="monotone"
              dataKey="bestScore"
              stroke="#eab308"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#eab308" }}
              name="bestScore"
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
      {/* Legend + stats */}
      <div className="mt-1 flex items-center justify-center gap-4 text-[10px] text-slate-600">
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 bg-amber-400" />
          最优分数
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
      {/* Summary stats bar */}
      <div className="mt-2 flex items-center justify-center gap-4 text-[10px]">
        <span className="text-slate-500">
          最优刷新 {totalChampionChanges} 次
        </span>
        <span className={maxStagnation > 10 ? "text-orange-400" : "text-slate-500"}>
          最长停滞 {maxStagnation} 代
        </span>
        {lastRecord?.fallbackPct != null && lastRecord.fallbackPct > 0 && (
          <span className="text-red-400/70">
            Fallback {lastRecord.fallbackPct}%
          </span>
        )}
      </div>
    </div>
  );
}
