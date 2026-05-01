import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { TrendingUp, Pause, Play, Square, Eye } from "lucide-react";
import { PageTransition } from "@/components/PageTransition";
import { GlassCard } from "@/components/GlassCard";
import { StatCard } from "@/components/StatCard";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import {
  useTradingTasks,
  useTradingTrades,
  useStopTradingTask,
  usePauseTradingTask,
  useResumeTradingTask,
  useCreateTradingTask,
  useTradingWebSocket,
} from "@/hooks/useTrading";
import type { TradingTask } from "@/services/trading";

type TrendDirection = "up" | "down" | "neutral";
type PositionSide = "long" | "short" | "flat";

const POSITION_BADGE_MAP: Record<PositionSide, { label: string; className: string }> = {
  long: { label: "多头", className: "text-profit border-profit/30" },
  short: { label: "空头", className: "text-loss border-loss/30" },
  flat: { label: "空仓", className: "text-text-muted border-border-default" },
};

const STATUS_BADGE_MAP: Record<string, { label: string; className: string }> = {
  pending: { label: "等待中", className: "text-accent-gold border-accent-gold/30" },
  running: { label: "运行中", className: "text-profit border-profit/30" },
  paused: { label: "已暂停", className: "text-accent-gold border-accent-gold/30" },
  stopped: { label: "已停止", className: "text-loss border-loss/30" },
  completed: { label: "已完成", className: "text-text-muted border-border-default" },
};

function getReturnTrend(value: number): TrendDirection {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "neutral";
}

function toPositionSide(side: string | null): PositionSide {
  if (side === "long") return "long";
  if (side === "short") return "short";
  return "flat";
}

export function Trading() {
  const { data: taskList, isLoading } = useTradingTasks();
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const createTask = useCreateTradingTask();

  const tasks = taskList?.tasks ?? [];
  const activeTaskId =
    selectedTaskId ?? tasks.find((t) => t.status === "running")?.task_id ?? null;

  useTradingWebSocket(activeTaskId);

  // Auto-create task from route state (e.g. navigated from Strategies)
  useEffect(() => {
    const state = location.state as {
      dna?: unknown;
      symbol?: string;
      timeframe?: string;
      strategyName?: string;
    } | null;

    if (state?.dna) {
      createTask.mutate({
        dna_json: typeof state.dna === "string" ? state.dna : JSON.stringify(state.dna),
        symbol: state.symbol || "BTCUSDT",
        timeframe: state.timeframe || "4h",
        strategy_name: state.strategyName,
      });
      window.history.replaceState({}, "");
    }
  }, []);

  if (isLoading) {
    return (
      <PageTransition>
        <div className="flex items-center justify-center h-64">
          <span className="text-text-muted">加载中...</span>
        </div>
      </PageTransition>
    );
  }

  if (tasks.length === 0) {
    return (
      <PageTransition>
        <EmptyState
          icon={TrendingUp}
          title="还没有模拟交易任务"
          description="前往策略库选择策略开始模拟交易，实时跟踪策略表现和持仓状态。"
          actions={[
            {
              label: "前往策略库",
              onClick: () => navigate("/strategies"),
              variant: "outline",
            },
          ]}
        />
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="flex flex-col gap-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">模拟交易</h2>
        </div>

        {/* Running strategies grid */}
        <div>
          <h3 className="mb-3 text-sm font-medium text-text-secondary">
            交易任务 ({tasks.length})
          </h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {tasks.map((task) => (
              <TaskCard
                key={task.task_id}
                task={task}
                isSelected={task.task_id === activeTaskId}
                onSelect={() => setSelectedTaskId(task.task_id)}
              />
            ))}
          </div>
        </div>

        {/* Selected task detail */}
        {activeTaskId && <TaskDetail taskId={activeTaskId} />}
      </div>
    </PageTransition>
  );
}

// ---------------------------------------------------------------------------
// Task Card
// ---------------------------------------------------------------------------

interface TaskCardProps {
  task: TradingTask;
  isSelected: boolean;
  onSelect: () => void;
}

function TaskCard({ task, isSelected, onSelect }: TaskCardProps) {
  const stopMut = useStopTradingTask();
  const pauseMut = usePauseTradingTask();
  const resumeMut = useResumeTradingTask();

  const posSide = toPositionSide(task.position_side);
  const posBadge = POSITION_BADGE_MAP[posSide];
  const statusBadge = STATUS_BADGE_MAP[task.status] ?? STATUS_BADGE_MAP.stopped;
  const returnRate = task.initial_cash > 0
    ? (task.total_pnl || 0) / task.initial_cash
    : 0;
  const trend = getReturnTrend(returnRate);
  const isRunning = task.status === "running";
  const isPaused = task.status === "paused";
  const isActive = isRunning || isPaused || task.status === "pending";

  return (
    <GlassCard
      className={cn("flex flex-col gap-3 cursor-pointer transition-all", isSelected && "ring-1 ring-accent-gold/30")}
      hover={false}
      onClick={onSelect}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-text-primary">
            {task.strategy_name || task.symbol}
          </span>
          <span className="text-xs text-text-muted">
            {task.symbol} / {task.timeframe} / {task.leverage}x
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Badge variant="outline" className={cn("h-5 text-[10px]", statusBadge.className)}>
            {statusBadge.label}
          </Badge>
          {posSide !== "flat" && (
            <Badge variant="outline" className={cn("h-5 text-[10px]", posBadge.className)}>
              {posBadge.label}
            </Badge>
          )}
        </div>
      </div>

      {/* Balance & PnL */}
      <div className="flex items-end justify-between">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-text-secondary">余额</span>
          <span className="text-base font-num font-semibold text-text-primary">
            {formatCurrency(task.balance ?? task.initial_cash)}
          </span>
        </div>
        <span
          className={cn(
            "font-num text-sm font-medium",
            trend === "up" && "text-profit",
            trend === "down" && "text-loss",
            trend === "neutral" && "text-text-primary"
          )}
        >
          {formatPercent(returnRate)}
        </span>
      </div>

      <Progress
        value={Math.min(Math.abs(returnRate) * 100, 100)}
        className={cn(
          "h-1.5",
          trend === "up" && "[&>[data-slot=progress-indicator]]:bg-profit",
          trend === "down" && "[&>[data-slot=progress-indicator]]:bg-loss",
          trend === "neutral" && "[&>[data-slot=progress-indicator]]:bg-text-muted"
        )}
      />

      {/* Stats */}
      <div className="flex items-center gap-3 text-xs text-text-muted">
        <span>{task.total_trades} 笔交易</span>
        <span>{task.win_count} 胜 / {task.loss_count} 负</span>
      </div>

      {/* Actions */}
      {isActive && (
        <div className="flex items-center gap-2 pt-1" onClick={(e) => e.stopPropagation()}>
          {isRunning && (
            <Button
              variant="outline"
              size="xs"
              className="gap-1 text-xs"
              onClick={() => pauseMut.mutate(task.task_id)}
            >
              <Pause className="h-3 w-3" />
              暂停
            </Button>
          )}
          {isPaused && (
            <Button
              variant="outline"
              size="xs"
              className="gap-1 text-xs"
              onClick={() => resumeMut.mutate(task.task_id)}
            >
              <Play className="h-3 w-3" />
              恢复
            </Button>
          )}
          <Button
            variant="ghost"
            size="xs"
            className="gap-1 text-xs text-loss"
            onClick={() => stopMut.mutate(task.task_id)}
          >
            <Square className="h-3 w-3" />
            停止
          </Button>
        </div>
      )}
    </GlassCard>
  );
}

// ---------------------------------------------------------------------------
// Task Detail Panel
// ---------------------------------------------------------------------------

function TaskDetail({ taskId }: { taskId: string }) {
  const { data: tradeData } = useTradingTrades(taskId, 20);

  // Find the task from the task list
  // We rely on the parent's query cache for the task data
  const trades = tradeData?.trades ?? [];

  return (
    <div>
      <h3 className="mb-3 text-sm font-medium text-text-secondary">
        交易记录
      </h3>
      {trades.length === 0 ? (
        <div className="flex items-center justify-center h-24 rounded-lg border border-border-default">
          <span className="text-sm text-text-muted">暂无交易记录</span>
        </div>
      ) : (
        <div className="rounded-lg border border-border-default overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-[#0f0f18] hover:bg-[#0f0f18]">
                <TableHead className="text-text-secondary">时间</TableHead>
                <TableHead className="text-text-secondary">方向</TableHead>
                <TableHead className="text-text-secondary">操作</TableHead>
                <TableHead className="text-text-secondary">价格</TableHead>
                <TableHead className="text-text-secondary">数量</TableHead>
                <TableHead className="text-text-secondary">盈亏</TableHead>
                <TableHead className="text-text-secondary">原因</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {trades.map((trade) => (
                <TradeRow key={trade.id} trade={trade} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

interface TradeRowProps {
  trade: {
    id: number;
    bar_time: string;
    side: string;
    action: string;
    price: number;
    quantity: number;
    pnl: number | null;
    reason: string | null;
  };
}

function TradeRow({ trade }: TradeRowProps) {
  const pnlTrend = trade.pnl !== null ? getReturnTrend(trade.pnl) : "neutral";
  const actionLabel: Record<string, string> = {
    open: "开仓",
    close: "平仓",
    add: "加仓",
    reduce: "减仓",
  };
  const sideLabel: Record<string, string> = {
    long: "多",
    short: "空",
    "": "-",
  };

  return (
    <TableRow>
      <TableCell>
        <span className="text-xs text-text-muted">
          {trade.bar_time.slice(0, 19).replace("T", " ")}
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-primary">
          {sideLabel[trade.side] ?? trade.side}
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-primary">
          {actionLabel[trade.action] ?? trade.action}
        </span>
      </TableCell>
      <TableCell>
        <span className="font-num text-sm text-text-primary">
          {formatCurrency(trade.price)}
        </span>
      </TableCell>
      <TableCell>
        <span className="font-num text-sm text-text-primary">
          {trade.quantity.toFixed(4)}
        </span>
      </TableCell>
      <TableCell>
        {trade.pnl !== null ? (
          <span
            className={cn(
              "font-num text-sm font-medium",
              pnlTrend === "up" && "text-profit",
              pnlTrend === "down" && "text-loss",
              pnlTrend === "neutral" && "text-text-primary"
            )}
          >
            {formatCurrency(trade.pnl)}
          </span>
        ) : (
          <span className="text-text-muted">-</span>
        )}
      </TableCell>
      <TableCell>
        <span className="text-xs text-text-muted">
          {trade.reason ?? "-"}
        </span>
      </TableCell>
    </TableRow>
  );
}
