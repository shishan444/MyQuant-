import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
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
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string }>;
  label?: number;
}) {
  if (!active || !payload) return null;
  return (
    <div className="rounded-lg border border-slate-700/50 bg-[#0d1117]/95 px-3 py-2 text-xs">
      <p className="mb-1 font-medium text-slate-300">第 {label} 代</p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color }}>
          {entry.name === "bestScore" ? "最优分数" : "平均分数"}:{" "}
          {entry.value.toFixed(1)}
        </p>
      ))}
    </div>
  );
}

export function ScoreTrendChart({
  records,
  targetScore,
}: ScoreTrendChartProps) {
  const data: ChartDataPoint[] = records.map((r) => ({
    generation: r.generation,
    bestScore: r.best_score,
    avgScore: r.avg_score,
  }));

  if (data.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center">
        <span className="text-xs text-slate-600">暂无趋势数据</span>
      </div>
    );
  }

  return (
    <div className="h-[200px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
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
        </LineChart>
      </ResponsiveContainer>
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
      </div>
    </div>
  );
}
