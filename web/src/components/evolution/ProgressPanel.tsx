import { Pause, Square, Play } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Progress } from "@/components/ui/progress";
import { StatCard } from "@/components/StatCard";
import { cn, formatNumber } from "@/lib/utils";
import { STATUS_LABELS as STATUS_LABEL, isActiveStatus } from "@/lib/constants";
import type { EvolutionTask } from "@/types/api";

interface ProgressPanelProps {
  task: EvolutionTask;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  pausePending: boolean;
  stopPending: boolean;
  resumePending: boolean;
}

export function ProgressPanel({
  task,
  onPause,
  onResume,
  onStop,
  pausePending,
  stopPending,
  resumePending,
}: ProgressPanelProps) {
  const currentGeneration = task.current_generation ?? 0;
  const maxGenerations = task.max_generations ?? 1;
  const progressPercent =
    maxGenerations > 0
      ? Math.round((currentGeneration / maxGenerations) * 100)
      : 0;
  const bestScore = task.best_score ?? 0;
  const targetScore = task.target_score ?? 0;
  const attemptedCount = currentGeneration * (task.population_size ?? 15);
  const isActive = isActiveStatus(task.status);
  const isPaused = task.status === "paused";
  const reachedTarget = bestScore >= targetScore;

  return (
    <div className="flex flex-col gap-4">
      {/* Status bar */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "inline-block h-2 w-2 rounded-full",
              task.status === "running" && "bg-blue-400 animate-pulse",
              task.status === "pending" && "bg-slate-500 animate-pulse",
              task.status === "paused" && "bg-amber-400",
              task.status === "stopped" && "bg-slate-500",
              task.status === "completed" && "bg-emerald-400"
            )}
          />
          <span className="text-xs font-medium text-slate-100">
            {STATUS_LABEL[task.status]}
          </span>
        </div>
        <span className="text-xs text-slate-500">
          已探索:{" "}
          <span className="font-mono text-slate-400">
            {attemptedCount.toLocaleString()}
          </span>{" "}
          组
        </span>
        <span className="text-xs text-slate-500">
          第 <span className="font-mono text-slate-400">{currentGeneration}</span>{" "}
          代 / {maxGenerations} 代
        </span>
      </div>

      {/* Progress bar */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500">
            进度
          </span>
          <span className="font-mono text-slate-400">
            {progressPercent}%
          </span>
        </div>
        <Progress
          value={progressPercent}
          className={cn(
            "h-2",
            reachedTarget
              ? "bg-emerald-400/10 [&>[data-slot=progress-indicator]]:bg-gradient-to-r [&>[data-slot=progress-indicator]]:from-emerald-400/80 [&>[data-slot=progress-indicator]]:to-amber-400/80"
              : "bg-amber-400/10 [&>[data-slot=progress-indicator]]:bg-gradient-to-r [&>[data-slot=progress-indicator]]:from-blue-500 [&>[data-slot=progress-indicator]]:to-purple-500"
          )}
        />
      </div>

      {/* Score comparison */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard
          label="当前最优"
          value={formatNumber(bestScore)}
          trend={reachedTarget ? "up" : "neutral"}
        />
        <StatCard
          label="目标分数"
          value={formatNumber(targetScore)}
          trend="neutral"
        />
      </div>

      {/* Control buttons */}
      {(isActive || isPaused) && (
        <div className="flex items-center gap-2">
          {isPaused ? (
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5"
              onClick={onResume}
              disabled={resumePending}
            >
              <Play className="h-3.5 w-3.5" />
              恢复
            </Button>
          ) : (
            <Button
              size="sm"
              variant="outline"
              className="gap-1.5"
              onClick={onPause}
              disabled={pausePending}
            >
              <Pause className="h-3.5 w-3.5" />
              暂停
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            className="gap-1.5 border-red-400/30 text-red-400 hover:bg-red-400/10"
            onClick={onStop}
            disabled={stopPending}
          >
            <Square className="h-3.5 w-3.5" />
            停止
          </Button>
        </div>
      )}
    </div>
  );
}
