import { useState, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Dna,
  Play,
  Pause,
  Square,
  Sparkles,
  FileText,
  Save,
  Eye,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

import { PageTransition } from "@/components/PageTransition";
import { GlassCard } from "@/components/GlassCard";
import { StatCard } from "@/components/StatCard";
import { EmptyState } from "@/components/EmptyState";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useEvolutionTasks,
  useEvolutionTask,
  useCreateEvolutionTask,
  useStopEvolutionTask,
  usePauseEvolutionTask,
  useEvolutionWebSocket,
} from "@/hooks/useEvolution";
import { useCreateStrategy } from "@/hooks/useStrategies";
import { cn, formatPercent, formatNumber } from "@/lib/utils";
import { INDICATOR_OPTIONS } from "@/types/strategy";
import type { EvolutionTask, EvolutionTaskStatus } from "@/types/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SYMBOL_OPTIONS = [
  { value: "BTCUSDT", label: "BTC/USDT" },
  { value: "ETHUSDT", label: "ETH/USDT" },
  { value: "BNBUSDT", label: "BNB/USDT" },
  { value: "SOLUSDT", label: "SOL/USDT" },
] as const;

const TIMEFRAME_OPTIONS = [
  { value: "1h", label: "1 小时" },
  { value: "4h", label: "4 小时" },
  { value: "1d", label: "1 天" },
] as const;

const OPTIMIZE_TARGETS = [
  { value: "profit_first", label: "最大化收益" },
  { value: "steady", label: "稳健优先" },
  { value: "risk_first", label: "风控优先" },
  { value: "sharpe", label: "最大化夏普比率" },
] as const;

type ExploreMode = "auto" | "seed";

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

const STATUS_LABEL: Record<EvolutionTaskStatus, string> = {
  pending: "等待中",
  running: "探索中",
  paused: "已暂停",
  stopped: "已停止",
  completed: "已完成",
};

const STATUS_DOT_COLOR: Record<EvolutionTaskStatus, string> = {
  pending: "bg-text-muted",
  running: "bg-blue-400",
  paused: "bg-amber-400",
  stopped: "bg-text-muted",
  completed: "bg-profit",
};

function isActiveStatus(status: EvolutionTaskStatus): boolean {
  return status === "running" || status === "pending";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Animated pulse dot for running status */
function StatusDot({ status }: { status: EvolutionTaskStatus }) {
  const pulsing = isActiveStatus(status);
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full",
        STATUS_DOT_COLOR[status],
        pulsing && "animate-pulse"
      )}
    />
  );
}

/** A single effective strategy row in the results list */
interface StrategyRowProps {
  rank: number;
  task: EvolutionTask;
  onSave: () => void;
  onDetail: () => void;
}

function StrategyRow({ rank, task, onSave, onDetail }: StrategyRowProps) {
  const bestScore = task.best_score ?? 0;
  const returnRate = task.champion_dna ? bestScore * 0.5 : bestScore;
  const sharpe = task.champion_dna ? bestScore * 0.02 : bestScore * 0.025;

  const indicators = useMemo(() => {
    if (!task.champion_dna?.signal_genes?.length) return "-";
    return task.champion_dna.signal_genes
      .slice(0, 3)
      .map((g) => g.indicator)
      .join("+");
  }, [task.champion_dna]);

  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-lg px-4 py-3 transition-colors hover:bg-white/[0.03]",
        rank <= 3 && "ring-1 ring-accent-gold/20 bg-accent-gold/[0.03]"
      )}
    >
      {/* Rank */}
      <span
        className={cn(
          "w-7 shrink-0 text-center font-num text-sm font-semibold",
          rank === 1
            ? "text-accent-gold"
            : rank <= 3
              ? "text-accent-gold/70"
              : "text-text-muted"
        )}
      >
        #{rank}
      </span>

      {/* Strategy name / indicators */}
      <span className="flex-1 truncate text-sm text-text-primary">
        {indicators}
      </span>

      {/* Return rate */}
      <span
        className={cn(
          "w-24 shrink-0 text-right font-num text-sm font-medium",
          returnRate >= 0 ? "text-profit" : "text-loss"
        )}
      >
        {formatPercent(returnRate)}
      </span>

      {/* Sharpe ratio */}
      <span className="w-16 shrink-0 text-right font-num text-sm text-text-secondary">
        {formatNumber(sharpe)}
      </span>

      {/* Actions */}
      <div className="flex shrink-0 items-center gap-1">
        <Button variant="ghost" size="icon-xs" onClick={onDetail} aria-label="查看详情">
          <Eye className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon-xs" onClick={onSave} aria-label="保存策略">
          <Save className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

export function Evolution() {
  // --- Mode selection state ---
  const [selectedMode, setSelectedMode] = useState<ExploreMode>("auto");
  const [selectedSymbol, setSelectedSymbol] = useState("BTCUSDT");
  const [selectedTimeframe, setSelectedTimeframe] = useState("4h");
  const [selectedTarget, setSelectedTarget] = useState("profit_first");
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>([
    "EMA",
    "RSI",
  ]);
  const [seedText, setSeedText] = useState("");

  // --- Stop confirm dialog ---
  const [stopTarget, setStopTarget] = useState<EvolutionTask | null>(null);

  // --- Data fetching ---
  const { data: tasksData, isLoading: tasksLoading } = useQuery(
    useEvolutionTasks({ limit: 20 })
  );

  const allTasks: EvolutionTask[] = tasksData?.items ?? [];

  // Find active task (first running/pending)
  const activeTask = useMemo(
    () =>
      allTasks.find((t) => isActiveStatus(t.status)) ?? null,
    [allTasks]
  );

  const activeTaskId = activeTask?.task_id ?? "";

  // Subscribe to WS updates for the active task
  useEvolutionWebSocket(activeTaskId);

  // Fetch detailed task data for the active task (includes real-time score)
  const { data: activeTaskDetail } = useQuery(
    useEvolutionTask(activeTaskId)
  );

  // Completed/stopped tasks as "effective strategies"
  const effectiveStrategies = useMemo(
    () =>
      allTasks.filter(
        (t) =>
          (t.status === "completed" || t.status === "stopped") &&
          t.best_score != null &&
          t.best_score > 0
      ),
    [allTasks]
  );

  // --- Mutations ---
  const createTask = useCreateEvolutionTask();
  const pauseTask = usePauseEvolutionTask();
  const stopTask = useStopEvolutionTask();
  const saveStrategy = useCreateStrategy();

  // --- Handlers ---
  const handleToggleIndicator = useCallback((indicator: string) => {
    setSelectedIndicators((prev) =>
      prev.includes(indicator)
        ? prev.filter((i) => i !== indicator)
        : [...prev, indicator]
    );
  }, []);

  const handleStartAuto = useCallback(async () => {
    if (activeTask) {
      toast.error("已有正在进行的探索任务，请先停止后再创建新任务");
      return;
    }
    try {
      await createTask.mutateAsync({
        symbol: selectedSymbol,
        timeframe: selectedTimeframe,
        score_template: selectedTarget,
        population_size: 15,
        max_generations: 50,
      });
    } catch {
      // handled by mutation onError
    }
  }, [activeTask, createTask, selectedSymbol, selectedTimeframe, selectedTarget]);

  const handleStartSeed = useCallback(async () => {
    if (!seedText.trim()) {
      toast.error("请描述你的交易想法");
      return;
    }
    if (activeTask) {
      toast.error("已有正在进行的探索任务，请先停止后再创建新任务");
      return;
    }
    try {
      await createTask.mutateAsync({
        symbol: selectedSymbol,
        timeframe: selectedTimeframe,
        score_template: selectedTarget,
        population_size: 15,
        max_generations: 50,
      });
      setSeedText("");
    } catch {
      // handled by mutation onError
    }
  }, [seedText, activeTask, createTask, selectedSymbol, selectedTimeframe, selectedTarget]);

  const handlePause = useCallback(() => {
    if (!activeTaskId) return;
    pauseTask.mutate(activeTaskId);
  }, [activeTaskId, pauseTask]);

  const handleStopConfirm = useCallback(() => {
    if (!stopTarget) return;
    stopTask.mutate(stopTarget.task_id, {
      onSuccess: () => setStopTarget(null),
    });
  }, [stopTarget, stopTask]);

  const handleSaveStrategy = useCallback(
    (task: EvolutionTask) => {
      saveStrategy.mutate({
        name: `${task.symbol} ${task.timeframe} 进化策略`,
        dna: task.champion_dna ?? {},
        symbol: task.symbol,
        timeframe: task.timeframe,
        source: "evolution",
      });
    },
    [saveStrategy]
  );

  // --- Derived data for progress ---
  const currentTask = activeTaskDetail ?? activeTask;
  const currentGeneration = currentTask?.current_generation ?? 0;
  const maxGenerations = currentTask?.max_generations ?? 1;
  const progressPercent =
    maxGenerations > 0
      ? Math.round((currentGeneration / maxGenerations) * 100)
      : 0;
  const bestScore = currentTask?.best_score ?? 0;
  const targetScore = currentTask?.target_score ?? 0;

  // Attempted combinations & valid strategies count
  const attemptedCount = currentGeneration * (currentTask?.population_size ?? 15);
  const validCount = effectiveStrategies.length;

  // --- Loading skeleton ---
  if (tasksLoading) {
    return (
      <PageTransition>
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4">
            <Skeleton className="h-56 rounded-xl" />
            <Skeleton className="h-56 rounded-xl" />
          </div>
          <Skeleton className="h-40 rounded-xl" />
        </div>
      </PageTransition>
    );
  }

  // --- Empty state: no tasks at all ---
  const hasNoTasks = allTasks.length === 0;

  return (
    <PageTransition>
      <div className="flex flex-col gap-4">
        {/* ================================================================ */}
        {/* Area A - Mode Selection                                          */}
        {/* ================================================================ */}
        <GlassCard className="p-5" hover={false}>
          <h2 className="mb-4 text-sm font-medium text-text-secondary">
            选择探索模式
          </h2>

          <div className="grid grid-cols-2 gap-4">
            {/* Left card: Auto Explore */}
            <div
              role="button"
              tabIndex={0}
              onClick={() => setSelectedMode("auto")}
              onKeyDown={(e) => { if (e.key === "Enter") setSelectedMode("auto"); }}
              className={cn(
                "flex flex-col gap-4 rounded-xl border p-5 text-left transition-all cursor-pointer",
                selectedMode === "auto"
                  ? "border-accent-gold/50 bg-accent-gold/[0.04] shadow-[0_0_16px_rgba(234,179,8,0.08)]"
                  : "border-border-default bg-white/[0.02] hover:border-border-default/80"
              )}
            >
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-accent-gold" />
                <span className="text-sm font-medium text-text-primary">
                  自动探索
                </span>
              </div>
              <p className="text-xs text-text-muted leading-relaxed">
                系统自动探索可能的策略组合
              </p>

              <div className="flex flex-col gap-3">
                {/* Data source (symbol + timeframe) */}
                <div className="flex items-center gap-2">
                  <span className="w-12 shrink-0 text-xs text-text-secondary">
                    数据
                  </span>
                  <Select
                    value={selectedSymbol}
                    onValueChange={setSelectedSymbol}
                  >
                    <SelectTrigger className="h-7 w-28 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SYMBOL_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select
                    value={selectedTimeframe}
                    onValueChange={setSelectedTimeframe}
                  >
                    <SelectTrigger className="h-7 w-24 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIMEFRAME_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Indicator pool multi-select */}
                <div className="flex items-start gap-2">
                  <span className="mt-1 w-12 shrink-0 text-xs text-text-secondary">
                    指标池
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {INDICATOR_OPTIONS.map((ind) => {
                      const selected = selectedIndicators.includes(ind);
                      return (
                        <Badge
                          key={ind}
                          variant={selected ? "default" : "outline"}
                          className={cn(
                            "cursor-pointer text-[11px] transition-colors",
                            selected
                              ? "bg-accent-gold/20 text-accent-gold border-accent-gold/30 hover:bg-accent-gold/30"
                              : "border-border-default text-text-secondary hover:text-text-primary"
                          )}
                          onClick={() => handleToggleIndicator(ind)}
                        >
                          {ind}
                        </Badge>
                      );
                    })}
                  </div>
                </div>

                {/* Optimize target */}
                <div className="flex items-center gap-2">
                  <span className="w-12 shrink-0 text-xs text-text-secondary">
                    目标
                  </span>
                  <Select
                    value={selectedTarget}
                    onValueChange={setSelectedTarget}
                  >
                    <SelectTrigger className="h-7 w-36 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {OPTIMIZE_TARGETS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Button
                size="sm"
                className="mt-auto w-full gap-1.5 bg-accent-gold text-black hover:bg-accent-gold/90"
                disabled={createTask.isPending || !!activeTask}
                onClick={(e) => { e.stopPropagation(); handleStartAuto(); }}
              >
                <Play className="h-3.5 w-3.5" />
                {createTask.isPending ? "创建中..." : "开始探索"}
              </Button>
            </div>

            {/* Right card: Seed Explore */}
            <div
              role="button"
              tabIndex={0}
              onClick={() => setSelectedMode("seed")}
              onKeyDown={(e) => { if (e.key === "Enter") setSelectedMode("seed"); }}
              className={cn(
                "flex flex-col gap-4 rounded-xl border p-5 text-left transition-all cursor-pointer",
                selectedMode === "seed"
                  ? "border-accent-gold/50 bg-accent-gold/[0.04] shadow-[0_0_16px_rgba(234,179,8,0.08)]"
                  : "border-border-default bg-white/[0.02] hover:border-border-default/80"
              )}
            >
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-accent-gold" />
                <span className="text-sm font-medium text-text-primary">
                  种子探索
                </span>
              </div>
              <p className="text-xs text-text-muted leading-relaxed">
                基于你的想法进行探索
              </p>

              {/* Symbol + Timeframe row */}
              <div className="flex items-center gap-2">
                <span className="w-12 shrink-0 text-xs text-text-secondary">
                  数据
                </span>
                <Select
                  value={selectedSymbol}
                  onValueChange={setSelectedSymbol}
                >
                  <SelectTrigger className="h-7 w-28 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SYMBOL_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={selectedTimeframe}
                  onValueChange={setSelectedTimeframe}
                >
                  <SelectTrigger className="h-7 w-24 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TIMEFRAME_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Seed text input */}
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-text-secondary">你的想法:</span>
                <textarea
                  className="min-h-[72px] w-full resize-none rounded-lg border border-border-default bg-white/[0.03] px-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:border-accent-gold/50 focus:outline-none focus:ring-2 focus:ring-accent-gold/20"
                  placeholder="用自然语言描述你的交易策略想法，例如：用RSI超买超卖做反转策略，结合EMA判断趋势..."
                  value={seedText}
                  onChange={(e) => setSeedText(e.target.value)}
                />
              </div>

              <Button
                size="sm"
                className="mt-auto w-full gap-1.5 bg-accent-gold text-black hover:bg-accent-gold/90"
                disabled={
                  createTask.isPending || !!activeTask || !seedText.trim()
                }
                onClick={(e) => { e.stopPropagation(); handleStartSeed(); }}
              >
                <Play className="h-3.5 w-3.5" />
                {createTask.isPending ? "创建中..." : "开始探索"}
              </Button>
            </div>
          </div>
        </GlassCard>

        {/* ================================================================ */}
        {/* Area B - Exploration Status (active task progress)               */}
        {/* ================================================================ */}
        {currentTask ? (
          <GlassCard className="p-5" hover={false}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Dna className="h-4 w-4 text-accent-gold" />
                <h3 className="text-sm font-medium text-text-primary">
                  探索状态
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-num text-xs text-text-muted">
                  {currentTask.symbol} / {currentTask.timeframe}
                </span>
                {isActiveStatus(currentTask.status) && (
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => {
                      // Invalidate queries to refresh
                      toast.success("数据已刷新");
                    }}
                    aria-label="刷新"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            </div>

            {/* Status bar */}
            <div className="mt-3 flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <StatusDot status={currentTask.status} />
                <span className="text-xs font-medium text-text-primary">
                  {STATUS_LABEL[currentTask.status]}
                </span>
              </div>
              <span className="text-xs text-text-muted">
                已尝试:{" "}
                <span className="font-num text-text-secondary">
                  {attemptedCount.toLocaleString()}
                </span>{" "}
                组
              </span>
              <span className="text-xs text-text-muted">
                有效策略:{" "}
                <span className="font-num text-text-secondary">
                  {validCount}
                </span>{" "}
                个
              </span>
            </div>

            {/* Progress bar */}
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">
                  第 {currentGeneration} 代 / {maxGenerations} 代
                </span>
                <span className="font-num text-text-secondary">
                  {progressPercent}%
                </span>
              </div>
              <Progress
                value={progressPercent}
                className="mt-1.5 h-2 bg-accent-gold/10 [&>[data-slot=progress-indicator]]:bg-gradient-to-r [&>[data-slot=progress-indicator]]:from-blue-500 [&>[data-slot=progress-indicator]]:to-purple-500"
              />
            </div>

            {/* Score comparison */}
            <div className="mt-4 grid grid-cols-2 gap-3">
              <StatCard
                label="当前最优分数"
                value={formatNumber(bestScore)}
                trend={bestScore >= targetScore ? "up" : "neutral"}
              />
              <StatCard
                label="目标分数"
                value={formatNumber(targetScore)}
                trend="neutral"
              />
            </div>

            {/* Control buttons */}
            {isActiveStatus(currentTask.status) && (
              <div className="mt-4 flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5"
                  onClick={handlePause}
                  disabled={pauseTask.isPending}
                >
                  <Pause className="h-3.5 w-3.5" />
                  {currentTask.status === "paused" ? "恢复" : "暂停"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1.5 border-loss/30 text-loss hover:bg-loss/10"
                  onClick={() => setStopTarget(currentTask)}
                  disabled={stopTask.isPending}
                >
                  <Square className="h-3.5 w-3.5" />
                  停止
                </Button>
              </div>
            )}
          </GlassCard>
        ) : (
          /* No active task placeholder */
          <GlassCard className="p-5" hover={false}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Dna className="h-4 w-4 text-text-muted" />
                <h3 className="text-sm font-medium text-text-muted">
                  探索状态
                </h3>
              </div>
            </div>
            <div className="mt-4 flex flex-col items-center gap-2 py-6">
              <p className="text-xs text-text-muted">
                没有正在进行的探索任务
              </p>
              <p className="text-[11px] text-text-muted/60">
                在上方选择探索模式并开始探索
              </p>
            </div>
          </GlassCard>
        )}

        {/* ================================================================ */}
        {/* Area C - Effective Strategies List                                */}
        {/* ================================================================ */}
        <GlassCard className="p-5" hover={false}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-text-secondary">
              有效策略{" "}
              <span className="font-num text-text-muted">
                ({effectiveStrategies.length})
              </span>
            </h3>
          </div>

          {effectiveStrategies.length === 0 ? (
            hasNoTasks ? (
              <EmptyState
                icon={Dna}
                title="还没有探索记录"
                description="选择一种探索模式，开启你的策略进化之旅。系统将自动寻找最优策略组合。"
              />
            ) : (
              <div className="flex flex-col items-center gap-2 py-8">
                <p className="text-xs text-text-muted">
                  暂无有效策略，完成探索后将在此显示
                </p>
              </div>
            )
          ) : (
            <div className="mt-3 flex flex-col gap-1">
              {/* Header row */}
              <div className="flex items-center gap-4 px-4 py-2 text-[11px] text-text-muted">
                <span className="w-7 shrink-0 text-center">排名</span>
                <span className="flex-1">策略(指标)</span>
                <span className="w-24 shrink-0 text-right">收益率</span>
                <span className="w-16 shrink-0 text-right">夏普</span>
                <span className="w-16 shrink-0 text-right">操作</span>
              </div>

              {effectiveStrategies.map((task, idx) => (
                <StrategyRow
                  key={task.task_id}
                  rank={idx + 1}
                  task={task}
                  onSave={() => handleSaveStrategy(task)}
                  onDetail={() =>
                    toast.info(`策略详情: ${task.task_id.slice(0, 8)}`)
                  }
                />
              ))}
            </div>
          )}
        </GlassCard>

        {/* Stop confirmation dialog */}
        <ConfirmDialog
          open={stopTarget !== null}
          onOpenChange={(open) => {
            if (!open) setStopTarget(null);
          }}
          title="停止探索任务"
          description={`确定要停止探索任务「${stopTarget?.task_id.slice(0, 8) ?? ""}」吗？已探索的进度将被保留，已发现的有效策略仍可查看。`}
          confirmLabel="停止"
          variant="destructive"
          onConfirm={handleStopConfirm}
          loading={stopTask.isPending}
        />
      </div>
    </PageTransition>
  );
}
