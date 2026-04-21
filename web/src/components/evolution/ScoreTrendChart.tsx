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
  prevBestScore?: number;
  isChampionChange?: boolean;
  stagnationCount?: number;
  avgTrades?: number;
  diversity?: number;
}

function parseDiagnostics(top3Summary?: string): {
  avgTrades?: number;
  diversity?: number;
} {
  if (!top3Summary) return {};
  try {
    const match = top3Summary.match(/diag=(\{.*\})/);
    if (match) {
      const raw = JSON.parse(match[1]) as Record<string, unknown>;
      // Map snake_case -> camelCase
      const avgTrades =
        typeof raw.avg_trades === "number" ? raw.avg_trades : undefined;
      // diversity: was float, now may be {genotype, signal, score}
      const rawDiv = raw.diversity;
      const diversity =
        typeof rawDiv === "number"
          ? rawDiv
          : typeof rawDiv === "object" && rawDiv !== null
            ? (rawDiv as Record<string, unknown>).genotype as number
            : undefined;
      return { avgTrades, diversity };
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
  if (!dataPoint) return null;

  const delta = dataPoint.prevBestScore != null
    ? dataPoint.bestScore - dataPoint.prevBestScore
    : undefined;
  const diversityPct = dataPoint.diversity != null
    ? `${(dataPoint.diversity * 100).toFixed(0)}%`
    : null;

  return (
    <div className="rounded-lg border border-slate-700/50 bg-[#0d1117]/95 px-3 py-2 text-xs min-w-[140px]">
      <p className="mb-1.5 font-medium text-slate-300">第 {label} 代</p>

      {/* Best score with delta */}
      <p className="text-amber-400">
        最优分数: {dataPoint.bestScore.toFixed(1)}
        {delta != null && delta !== 0 && (
          <span className={delta > 0 ? "text-emerald-400 ml-1" : "text-red-400/70 ml-1"}>
            {delta > 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1)}
          </span>
        )}
      </p>

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

      {/* Stagnation */}
      {dataPoint.stagnationCount != null && dataPoint.stagnationCount > 0 && (
        <p className="text-orange-400/70">
          停滞: {dataPoint.stagnationCount} 代未突破
        </p>
      )}

      {/* Breakthrough indicator */}
      {dataPoint.isChampionChange && (
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

    // Detect champion changes and record prevBestScore for delta
    let prevBest = -Infinity;
    const changes: ChartDataPoint[] = [];
    for (const point of chartData) {
      if (prevBest !== -Infinity) {
        point.prevBestScore = prevBest;
      }
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
      </div>
    </div>
  );
}
