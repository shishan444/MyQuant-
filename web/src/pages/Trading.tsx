import { useState, useEffect, useCallback } from "react";
import { useLocation, useNavigate } from "react-router";
import { TrendingUp, Pause, Play, Square, Trash2, Plus, RotateCcw } from "lucide-react";
import { PageTransition } from "@/components/PageTransition";
import { GlassCard } from "@/components/GlassCard";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import {
  useTradingTasks,
  useTradingTrades,
  useStopTradingTask,
  usePauseTradingTask,
  useResumeTradingTask,
  useCreateTradingTask,
  useRestartTradingTask,
  useDeleteTradingTask,
  useTradingWebSocket,
  useTradingEquity,
  useTradingMetrics,
  useRunnerStatus,
} from "@/hooks/useTrading";
import { TradingChart } from "@/components/trading/TradingChart";
import { EquityCurve } from "@/components/trading/EquityCurve";
import { MetricsDashboard } from "@/components/trading/MetricsDashboard";
import { RunnerStatusBadge } from "@/components/trading/RunnerStatusBadge";
import { CreateTaskDialog } from "@/components/trading/CreateTaskDialog";
import type { TradingTask, PaperTrade } from "@/services/trading";

type PositionSide = "long" | "short" | "flat";

const POSITION_BADGE_MAP: Record<PositionSide, { label: string; className: string }> = {
  long: { label: "Long", className: "text-profit border-profit/30" },
  short: { label: "Short", className: "text-loss border-loss/30" },
  flat: { label: "Flat", className: "text-text-muted border-border-default" },
};

const STATUS_BADGE_MAP: Record<string, { label: string; className: string }> = {
  pending: { label: "Pending", className: "text-accent-gold border-accent-gold/30" },
  running: { label: "Running", className: "text-profit border-profit/30" },
  paused: { label: "Paused", className: "text-accent-gold border-accent-gold/30" },
  stopped: { label: "Stopped", className: "text-loss border-loss/30" },
};

function toPositionSide(side: string | null): PositionSide {
  if (side === "long") return "long";
  if (side === "short") return "short";
  return "flat";
}

// ---------------------------------------------------------------------------
// Position Info Card
// ---------------------------------------------------------------------------

function PositionInfoCard({ task }: { task: TradingTask }) {
  const posSide = toPositionSide(task.position_side);
  if (posSide === "flat") return null;

  const entry = task.position_entry;
  const qty = task.position_quantity;
  const margin = task.position_margin;
  const upnl = task.unrealized_pnl;

  return (
    <GlassCard className="flex items-center gap-6 p-3 text-sm">
      <div>
        <span className="text-[10px] text-text-muted">Entry</span>
        <p className="font-num text-text-primary">{entry != null ? formatCurrency(entry) : "-"}</p>
      </div>
      <div>
        <span className="text-[10px] text-text-muted">Quantity</span>
        <p className="font-num text-text-primary">{qty != null ? qty.toFixed(6) : "-"}</p>
      </div>
      <div>
        <span className="text-[10px] text-text-muted">Margin</span>
        <p className="font-num text-text-primary">{margin != null ? formatCurrency(margin) : "-"}</p>
      </div>
      <div>
        <span className="text-[10px] text-text-muted">Unrealized PnL</span>
        <p className={cn("font-num font-medium", upnl > 0 ? "text-profit" : upnl < 0 ? "text-loss" : "text-text-primary")}>
          {formatCurrency(upnl)}
        </p>
      </div>
    </GlassCard>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function Trading() {
  const { data: taskList, isLoading } = useTradingTasks();
  const { data: runnerStatus } = useRunnerStatus();
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [restartTarget, setRestartTarget] = useState<TradingTask | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const createTask = useCreateTradingTask();
  const restartMut = useRestartTradingTask();
  const deleteMut = useDeleteTradingTask();

  const tasks = taskList?.tasks ?? [];
  const activeTaskId =
    selectedTaskId ?? tasks.find((t) => t.status === "running")?.task_id ?? null;

  const wsConnected = useTradingWebSocket(activeTaskId);

  // Route state for auto-create from Strategies page
  const [pendingCreate, setPendingCreate] = useState<{
    dna: string;
    symbol: string;
    timeframe: string;
    strategyName: string | null;
    initialCash: number;
  } | null>(null);

  useEffect(() => {
    const state = location.state as {
      dna?: unknown;
      symbol?: string;
      timeframe?: string;
      strategyName?: string;
      initialCash?: number;
    } | null;

    if (state?.dna) {
      setPendingCreate({
        dna: typeof state.dna === "string" ? state.dna : JSON.stringify(state.dna),
        symbol: state.symbol || "BTCUSDT",
        timeframe: state.timeframe || "4h",
        strategyName: state.strategyName ?? null,
        initialCash: state.initialCash ?? 100_000,
      });
      setDialogOpen(true);
      window.history.replaceState({}, "");
    }
  }, []);

  const handleConfirmCreate = useCallback((initialCash: number) => {
    if (pendingCreate) {
      createTask.mutate({
        dna_json: pendingCreate.dna,
        symbol: pendingCreate.symbol,
        timeframe: pendingCreate.timeframe,
        strategy_name: pendingCreate.strategyName ?? undefined,
        initial_cash: initialCash,
      });
      setPendingCreate(null);
    }
    setDialogOpen(false);
  }, [pendingCreate, createTask]);

  const handleRestart = useCallback(() => {
    if (!restartTarget) return;
    restartMut.mutate(restartTarget.task_id);
    setRestartTarget(null);
  }, [restartTarget, restartMut]);

  if (isLoading) {
    return (
      <PageTransition>
        <div className="flex items-center justify-center h-64">
          <span className="text-text-muted">Loading...</span>
        </div>
      </PageTransition>
    );
  }

  if (tasks.length === 0) {
    return (
      <PageTransition>
        <EmptyState
          icon={TrendingUp}
          title="No paper trading tasks"
          description="Go to the strategy library to select a strategy and start paper trading."
          actions={[
            {
              label: "Go to Strategies",
              onClick: () => navigate("/strategies"),
              variant: "outline",
            },
          ]}
        />
        <CreateTaskDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          strategyName={pendingCreate?.strategyName ?? null}
          symbol={pendingCreate?.symbol ?? "BTCUSDT"}
          timeframe={pendingCreate?.timeframe ?? "4h"}
          initialCash={pendingCreate?.initialCash ?? 100_000}
          onConfirm={handleConfirmCreate}
        />
      </PageTransition>
    );
  }

  const activeTask = tasks.find((t) => t.task_id === activeTaskId);

  return (
    <PageTransition>
      <div className="flex h-[calc(100vh-5rem)] gap-4">
        {/* Left sidebar: task list */}
        <div className="w-72 flex-shrink-0 flex flex-col gap-3 overflow-y-auto pr-1">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text-primary">Tasks</h2>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="xs"
                className="gap-1 text-xs text-accent-gold"
                onClick={() => navigate("/strategies")}
              >
                <Plus className="h-3 w-3" /> New
              </Button>
              <RunnerStatusBadge
                isAlive={runnerStatus?.is_alive ?? false}
                activeTaskId={runnerStatus?.active_task_id ?? null}
              />
            </div>
          </div>
          {tasks.map((task) => (
            <TaskListItem
              key={task.task_id}
              task={task}
              isSelected={task.task_id === activeTaskId}
              onSelect={() => setSelectedTaskId(task.task_id)}
              onDelete={() => setDeleteTarget(task.task_id)}
              onRestart={() => setRestartTarget(task)}
            />
          ))}
        </div>

        {/* Right panel: detail */}
        <div className="flex-1 flex flex-col gap-4 overflow-y-auto">
          {activeTask ? (
            <TaskDetailPanel
              task={activeTask}
              wsConnected={wsConnected}
              onRestart={() => setRestartTarget(activeTask)}
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <span className="text-sm text-text-muted">Select a task to view details</span>
            </div>
          )}
        </div>
      </div>

      {/* Create dialog */}
      <CreateTaskDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        strategyName={pendingCreate?.strategyName ?? null}
        symbol={pendingCreate?.symbol ?? "BTCUSDT"}
        timeframe={pendingCreate?.timeframe ?? "4h"}
        initialCash={pendingCreate?.initialCash ?? 100_000}
        onConfirm={handleConfirmCreate}
      />

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Task</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the task and all associated data (trades, equity snapshots). This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-loss text-white hover:bg-loss/80"
              disabled={deleteMut.isPending}
              onClick={() => {
                if (deleteTarget) {
                  deleteMut.mutate(deleteTarget);
                  if (selectedTaskId === deleteTarget) setSelectedTaskId(null);
                  setDeleteTarget(null);
                }
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Restart confirmation */}
      <AlertDialog open={!!restartTarget} onOpenChange={() => setRestartTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Restart Paper Trading</AlertDialogTitle>
            <AlertDialogDescription>
              Create a new task with the same strategy ({restartTarget?.strategy_name || restartTarget?.symbol}) on {restartTarget?.symbol} / {restartTarget?.timeframe}? Initial capital: {formatCurrency(restartTarget?.initial_cash ?? 100_000)}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={restartMut.isPending}
              onClick={handleRestart}
            >
              Create Task
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageTransition>
  );
}

// ---------------------------------------------------------------------------
// Task List Item (sidebar)
// ---------------------------------------------------------------------------

function TaskListItem({
  task,
  isSelected,
  onSelect,
  onDelete,
  onRestart,
}: {
  task: TradingTask;
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRestart: () => void;
}) {
  const posSide = toPositionSide(task.position_side);
  const statusBadge = STATUS_BADGE_MAP[task.status] ?? STATUS_BADGE_MAP.stopped;
  const returnRate = task.initial_cash > 0 ? (task.total_pnl || 0) / task.initial_cash : 0;
  const trend = returnRate > 0 ? "up" : returnRate < 0 ? "down" : "neutral";
  const isStopped = task.status === "stopped";

  return (
    <GlassCard
      className={cn(
        "flex flex-col gap-2 cursor-pointer transition-all p-3",
        isSelected && "ring-1 ring-accent-gold/30",
      )}
      hover={false}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="text-sm font-medium text-text-primary truncate">
            {task.strategy_name || task.symbol}
          </span>
          <span className="text-[10px] text-text-muted">
            {task.symbol} / {task.timeframe} / {task.leverage}x
          </span>
        </div>
        <Badge variant="outline" className={cn("h-4 text-[9px] shrink-0", statusBadge.className)}>
          {statusBadge.label}
        </Badge>
      </div>
      <div className="flex items-end justify-between">
        <span className="font-num text-sm font-semibold text-text-primary">
          {formatCurrency(task.balance ?? task.initial_cash)}
        </span>
        <span
          className={cn(
            "font-num text-xs font-medium",
            trend === "up" && "text-profit",
            trend === "down" && "text-loss",
            trend === "neutral" && "text-text-muted",
          )}
        >
          {formatPercent(returnRate)}
        </span>
      </div>
      {isStopped && (
        <div className="flex items-center gap-1 self-end">
          <Button
            variant="ghost"
            size="xs"
            className="text-accent-gold text-[10px] h-5 px-1"
            onClick={(e) => {
              e.stopPropagation();
              onRestart();
            }}
            title="Restart with same strategy"
          >
            <RotateCcw className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="xs"
            className="text-loss text-[10px] h-5 px-1"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      )}
    </GlassCard>
  );
}

// ---------------------------------------------------------------------------
// Task Detail Panel (right side)
// ---------------------------------------------------------------------------

const TRADE_PAGE_SIZE = 50;

function TaskDetailPanel({ task, wsConnected, onRestart }: {
  task: TradingTask;
  wsConnected: boolean;
  onRestart: () => void;
}) {
  const stopMut = useStopTradingTask();
  const pauseMut = usePauseTradingTask();
  const resumeMut = useResumeTradingTask();

  // Fetch more trades to support pagination
  const { data: tradeData } = useTradingTrades(task.task_id, 500);
  const { data: equityData } = useTradingEquity(task.task_id);
  const { data: metricsData } = useTradingMetrics(task.task_id);

  const trades = tradeData?.trades ?? [];
  const totalTrades = tradeData?.total ?? 0;
  const equitySnapshots = equityData?.snapshots ?? [];
  const isRunning = task.status === "running";
  const isPaused = task.status === "paused";
  const isActive = isRunning || isPaused || task.status === "pending";
  const isStopped = task.status === "stopped";
  const mutating = stopMut.isPending || pauseMut.isPending || resumeMut.isPending;

  const [visibleTrades, setVisibleTrades] = useState(TRADE_PAGE_SIZE);

  // Reset visible count when task changes
  useEffect(() => {
    setVisibleTrades(TRADE_PAGE_SIZE);
  }, [task.task_id]);

  const displayedTrades = trades.slice(0, visibleTrades);
  const hasMore = visibleTrades < trades.length;

  return (
    <div className="flex flex-col gap-4">
      {/* Header with controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-semibold text-text-primary">
            {task.strategy_name || task.symbol}
          </h2>
          <Badge variant="outline" className={cn("h-5 text-[10px]", STATUS_BADGE_MAP[task.status]?.className)}>
            {STATUS_BADGE_MAP[task.status]?.label ?? task.status}
          </Badge>
          {toPositionSide(task.position_side) !== "flat" && (
            <Badge variant="outline" className={cn("h-5 text-[10px]", POSITION_BADGE_MAP[toPositionSide(task.position_side)].className)}>
              {POSITION_BADGE_MAP[toPositionSide(task.position_side)].label}
            </Badge>
          )}
          {wsConnected && isRunning && (
            <span className="h-2 w-2 rounded-full bg-profit animate-pulse" title="WS Connected" />
          )}
        </div>
        <div className="flex items-center gap-2">
          {isActive && (
            <>
              {isRunning && (
                <Button variant="outline" size="xs" className="gap-1 text-xs" disabled={mutating} onClick={() => pauseMut.mutate(task.task_id)}>
                  <Pause className="h-3 w-3" /> Pause
                </Button>
              )}
              {isPaused && (
                <Button variant="outline" size="xs" className="gap-1 text-xs" disabled={mutating} onClick={() => resumeMut.mutate(task.task_id)}>
                  <Play className="h-3 w-3" /> Resume
                </Button>
              )}
              <Button variant="ghost" size="xs" className="gap-1 text-xs text-loss" disabled={mutating} onClick={() => stopMut.mutate(task.task_id)}>
                <Square className="h-3 w-3" /> Stop
              </Button>
            </>
          )}
          {isStopped && (
            <Button variant="outline" size="xs" className="gap-1 text-xs text-accent-gold" onClick={onRestart}>
              <RotateCcw className="h-3 w-3" /> Restart
            </Button>
          )}
        </div>
      </div>

      {/* Position info */}
      <PositionInfoCard task={task} />

      {/* Metrics */}
      <MetricsDashboard metrics={metricsData} initialCash={task.initial_cash} />

      {/* K-line chart with trade markers */}
      <TradingChart
        symbol={task.symbol}
        timeframe={task.timeframe}
        trades={trades}
        height={400}
        isActive={isActive}
      />

      {/* Equity curve */}
      {equitySnapshots.length > 0 && (
        <GlassCard className="p-3">
          <span className="text-xs text-text-secondary mb-2 block">Equity Curve</span>
          <EquityCurve data={equitySnapshots} initialCash={task.initial_cash} height={180} />
        </GlassCard>
      )}

      {/* Trade history */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-text-secondary">
          Trade History ({totalTrades})
        </h3>
        {trades.length === 0 ? (
          <div className="flex items-center justify-center h-20 rounded-lg border border-border-default">
            <span className="text-sm text-text-muted">No trades yet</span>
          </div>
        ) : (
          <div className="rounded-lg border border-border-default overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-[#0f0f18] hover:bg-[#0f0f18]">
                  <TableHead className="text-text-secondary">Time</TableHead>
                  <TableHead className="text-text-secondary">Side</TableHead>
                  <TableHead className="text-text-secondary">Action</TableHead>
                  <TableHead className="text-text-secondary">Price</TableHead>
                  <TableHead className="text-text-secondary">Qty</TableHead>
                  <TableHead className="text-text-secondary">PnL</TableHead>
                  <TableHead className="text-text-secondary">Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayedTrades.map((trade) => (
                  <TradeRow key={trade.id} trade={trade} />
                ))}
              </TableBody>
            </Table>
            {hasMore && (
              <div className="flex justify-center py-2 border-t border-border-default">
                <Button
                  variant="ghost"
                  size="xs"
                  className="text-xs text-text-muted"
                  onClick={() => setVisibleTrades((v) => v + TRADE_PAGE_SIZE)}
                >
                  Load More ({trades.length - visibleTrades} remaining)
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TradeRow
// ---------------------------------------------------------------------------

function TradeRow({ trade }: { trade: PaperTrade }) {
  const pnlTrend = trade.pnl !== null ? (trade.pnl > 0 ? "up" : trade.pnl < 0 ? "down" : "neutral") : "neutral";
  const actionLabel: Record<string, string> = { open: "Open", close: "Close", add: "Add", reduce: "Reduce" };
  const sideLabel: Record<string, string> = { long: "Long", short: "Short", "": "-" };
  const sideColor: Record<string, string> = { long: "text-profit", short: "text-loss", "": "" };

  return (
    <TableRow>
      <TableCell>
        <span className="text-xs text-text-muted">{trade.bar_time.slice(0, 19).replace("T", " ")}</span>
      </TableCell>
      <TableCell>
        <span className={cn("text-sm", sideColor[trade.side] ?? "text-text-primary")}>
          {sideLabel[trade.side] ?? trade.side}
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-primary">{actionLabel[trade.action] ?? trade.action}</span>
      </TableCell>
      <TableCell>
        <span className="font-num text-sm text-text-primary">{formatCurrency(trade.price)}</span>
      </TableCell>
      <TableCell>
        <span className="font-num text-sm text-text-primary">{trade.quantity.toFixed(4)}</span>
      </TableCell>
      <TableCell>
        {trade.pnl !== null ? (
          <span className={cn("font-num text-sm font-medium", pnlTrend === "up" && "text-profit", pnlTrend === "down" && "text-loss")}>
            {formatCurrency(trade.pnl)}
          </span>
        ) : (
          <span className="text-text-muted">-</span>
        )}
      </TableCell>
      <TableCell>
        <span className="text-xs text-text-muted">{trade.reason ?? "-"}</span>
      </TableCell>
    </TableRow>
  );
}
