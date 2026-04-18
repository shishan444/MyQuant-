import { useMemo, memo } from "react";
import { Eye, Dna } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/badge";
import { cn, formatNumber, formatDuration } from "@/lib/utils";
import { TIMEFRAME_LABELS, SCORE_TEMPLATE_LABELS, STOP_REASON_LABELS } from "@/lib/constants";
import type { EvolutionTask, DNA } from "@/types/api";

interface HistoryTableProps {
  tasks: EvolutionTask[];
  onViewTask: (taskId: string) => void;
  onSeedEvolve: (dna: DNA) => void;
}

export function HistoryTable({
  tasks,
  onViewTask,
  onSeedEvolve,
}: HistoryTableProps) {
  if (tasks.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-700/30 text-slate-500">
            <th className="py-2 text-left font-medium">交易对</th>
            <th className="py-2 text-left font-medium">周期</th>
            <th className="py-2 text-left font-medium">模式</th>
            <th className="py-2 text-left font-medium">杠杆</th>
            <th className="py-2 text-left font-medium">方向</th>
            <th className="py-2 text-left font-medium">目标</th>
            <th className="py-2 text-right font-medium">最优分</th>
            <th className="py-2 text-right font-medium">用时</th>
            <th className="py-2 text-center font-medium">状态</th>
            <th className="py-2 text-left font-medium">数据范围</th>
            <th className="py-2 text-center font-medium">可信度</th>
            <th className="py-2 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <HistoryRow
              key={task.task_id}
              task={task}
              onView={() => onViewTask(task.task_id)}
              onSeedEvolve={() =>
                task.champion_dna &&
                onSeedEvolve(task.champion_dna)
              }
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface HistoryRowProps {
  task: EvolutionTask;
  onView: () => void;
  onSeedEvolve: () => void;
}

const HistoryRow = memo(function HistoryRow({ task, onView, onSeedEvolve }: HistoryRowProps) {
  const timeframeDisplay = useMemo(() => {
    if (task.timeframe_pool && task.timeframe_pool.length > 1) {
      return task.timeframe_pool
        .map((tf) => TIMEFRAME_LABELS[tf] ?? tf)
        .join("+");
    }
    return TIMEFRAME_LABELS[task.timeframe] ?? task.timeframe;
  }, [task.timeframe, task.timeframe_pool]);

  const modeLabel = task.mode === "seed" ? "种子探索" : "自动探索";

  const targetLabel = useMemo(() => {
    return SCORE_TEMPLATE_LABELS[task.score_template] ?? task.score_template;
  }, [task.score_template]);

  const duration = useMemo(
    () => formatDuration(task.created_at, task.updated_at),
    [task.created_at, task.updated_at]
  );

  const isCompleted = task.status === "completed";
  const isStopped = task.status === "stopped";

  return (
    <tr className="group border-b border-slate-700/10 transition-colors hover:bg-white/[0.02]">
      <td className="py-3 text-slate-200">{task.symbol.replace("USDT", "")}</td>
      <td className="py-3 text-slate-300">{timeframeDisplay}</td>
      <td className="py-3">
        <Badge
          variant="outline"
          className="border-slate-700/50 text-[10px] text-slate-500"
        >
          {modeLabel}
        </Badge>
      </td>
      <td className="py-3 text-slate-400">{task.leverage}x</td>
      <td className="py-3">
        <Badge
          variant="outline"
          className={cn(
            "text-[10px]",
            task.direction === "short"
              ? "border-red-400/30 text-red-400"
              : task.direction === "mixed"
                ? "border-purple-400/30 text-purple-400"
                : "border-emerald-400/30 text-emerald-400"
          )}
        >
          {task.direction === "short" ? "做空" : task.direction === "mixed" ? "混合" : "做多"}
        </Badge>
      </td>
      <td className="py-3 text-slate-400">{targetLabel}</td>
      <td className="py-3 text-right font-mono font-semibold text-slate-200">
        {formatNumber(task.best_score ?? 0)}
      </td>
      <td className="py-3 text-right font-mono text-slate-500">{duration}</td>
      <td className="py-3 text-center">
        <Badge
          variant="outline"
          className={cn(
            "text-[10px]",
            isCompleted
              ? "border-emerald-400/30 text-emerald-400"
              : isStopped
                ? "border-slate-600/30 text-slate-500"
                : "border-slate-700/30 text-slate-500"
          )}
        >
          {isCompleted ? "已完成" : isStopped ? "已停止" : task.status}
        </Badge>
      </td>
      <td className="py-3 text-xs text-slate-500">
        {task.data_start || task.data_time_start
          ? `${(task.data_start || task.data_time_start)?.slice(0, 10) ?? ""} ~ ${(task.data_end || task.data_time_end)?.slice(0, 10) ?? ""}`
          : "-"}
      </td>
      <td className="py-3 text-center">
        <Badge
          variant="outline"
          className={cn(
            "text-[10px]",
            task.data_row_count && task.data_row_count > 500
              ? "border-emerald-400/30 text-emerald-400"
              : task.data_row_count && task.data_row_count > 0
                ? "border-amber-400/30 text-amber-400"
                : "border-red-400/30 text-red-400"
          )}
        >
          {task.data_row_count && task.data_row_count > 500
            ? "可信"
            : task.data_row_count && task.data_row_count > 0
              ? "数据偏少"
              : "未验证"}
        </Badge>
      </td>
      <td className="py-3 text-right">
        <div className="flex items-center justify-end gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={onView}
            aria-label="查看"
          >
            <Eye className="h-3.5 w-3.5" />
          </Button>
          {task.champion_dna && (
            <Button
              variant="ghost"
              size="icon-xs"
              className="text-purple-400"
              onClick={onSeedEvolve}
              aria-label="继续进化"
            >
              <Dna className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </td>
    </tr>
  );
});
