import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { DistributionBucket } from "@/types/api";

interface DistributionChartProps {
  distribution: DistributionBucket[];
}

interface ChartDataPoint {
  range: string;
  match: number;
  mismatch: number;
  total: number;
  rangeStart: number;
  rangeEnd: number;
}

function formatRange(bucket: DistributionBucket): string {
  const [start, end] = bucket.range;
  return `${start}%~${end}%`;
}

function CustomTooltip({ active, payload }: {
  active?: boolean;
  payload?: Array<{ payload: ChartDataPoint }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const matchRate = d.total > 0 ? ((d.match / d.total) * 100).toFixed(1) : "0";

  return (
    <div className="rounded-lg border border-border-default bg-bg-surface px-3 py-2 shadow-xl">
      <p className="mb-1 text-xs font-medium text-text-primary">
        区间: {d.range}
      </p>
      <p className="text-xs text-profit">符合: {d.match}次 ({matchRate}%)</p>
      <p className="text-xs text-loss">不符合: {d.mismatch}次</p>
      <p className="text-xs text-text-secondary">总计: {d.total}次</p>
    </div>
  );
}

export function DistributionChart({ distribution }: DistributionChartProps) {
  if (!distribution || distribution.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-text-muted">
        暂无分布数据
      </div>
    );
  }

  const data: ChartDataPoint[] = distribution.map((b) => ({
    range: formatRange(b),
    match: b.match_count,
    mismatch: b.mismatch_count,
    total: b.total_count,
    rangeStart: b.range[0],
    rangeEnd: b.range[1],
  }));

  return (
    <div>
      <h4 className="mb-3 text-sm font-semibold text-text-secondary">幅度区间分布</h4>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,37,48,0.5)" />
            <XAxis
              dataKey="range"
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              axisLine={{ stroke: "rgba(30,37,48,0.5)" }}
            />
            <YAxis
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              axisLine={{ stroke: "rgba(30,37,48,0.5)" }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar
              dataKey="match"
              stackId="stack"
              fill="rgba(0,200,83,0.5)"
              radius={[0, 0, 0, 0]}
            />
            <Bar
              dataKey="mismatch"
              stackId="stack"
              fill="rgba(239,68,68,0.5)"
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex items-center justify-center gap-4 text-[10px] text-text-muted">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-profit/50" />
          符合
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-loss/50" />
          不符合
        </span>
      </div>
    </div>
  );
}
