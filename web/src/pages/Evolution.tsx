import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Dna, Pause, Square, Play, RefreshCw,
  TrendingUp, Clock, Target,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { GenerationChart } from '@/components/evolution/GenerationChart';
import { MutationLog } from '@/components/evolution/MutationLog';
import { PopulationStatus } from '@/components/evolution/PopulationStatus';
import { getEvolutionTask, getEvolutionHistory, pauseEvolution, stopEvolution } from '@/api/evolution';
import type {
  EvolutionTaskDetail,
  GenerationHistoryPoint,
  WsEvolutionMessage,
  PopulationState,
  MutationLogEntry,
} from '@/types';

const POLL_INTERVAL = 5000;

const DEFAULT_POPULATION: PopulationState = {
  diversity: 0,
  score_distribution: [],
  elite_count: 0,
  total_count: 0,
};

function formatDuration(startTime: string): string {
  const start = new Date(startTime).getTime();
  const elapsed = Date.now() - start;
  const hours = Math.floor(elapsed / 3600000);
  const minutes = Math.floor((elapsed % 3600000) / 60000);
  const seconds = Math.floor((elapsed % 60000) / 1000);
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function getStatusBadge(status: string): { label: string; className: string } {
  switch (status) {
    case 'running':
      return { label: 'Running', className: 'bg-[var(--color-profit)]/20 text-[var(--color-profit)]' };
    case 'paused':
      return { label: 'Paused', className: 'bg-[var(--color-warn)]/20 text-[var(--color-warn)]' };
    case 'completed':
      return { label: 'Completed', className: 'bg-[var(--color-blue)]/20 text-[var(--color-blue)]' };
    case 'failed':
      return { label: 'Failed', className: 'bg-[var(--color-loss)]/20 text-[var(--color-loss)]' };
    default:
      return { label: 'Pending', className: 'bg-[var(--text-disabled)]/20 text-[var(--text-disabled)]' };
  }
}

export function Evolution() {
  const [task, setTask] = useState<EvolutionTaskDetail | null>(null);
  const [history, setHistory] = useState<GenerationHistoryPoint[]>([]);
  const [mutationLogs, setMutationLogs] = useState<MutationLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearConnections = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (elapsedRef.current) {
      clearInterval(elapsedRef.current);
      elapsedRef.current = null;
    }
  }, []);

  const fetchTaskData = useCallback(async (id: string) => {
    try {
      const [taskDetail, historyData] = await Promise.all([
        getEvolutionTask(id),
        getEvolutionHistory(id),
      ]);
      setTask(taskDetail);
      setHistory(historyData);
      setMutationLogs(taskDetail.mutation_logs ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch task data');
    }
  }, []);

  const startPolling = useCallback((id: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => {
      void fetchTaskData(id);
    }, POLL_INTERVAL);
  }, [fetchTaskData]);

  const connectWebSocket = useCallback((id: string) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/evolution/${id}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg: WsEvolutionMessage = JSON.parse(event.data as string);

        if (msg.type === 'generation_complete' && msg.mutation_log) {
          setMutationLogs((prev) => [...prev, msg.mutation_log!]);
        }

        // Refresh full data on any message
        void fetchTaskData(id);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => {
      ws.close();
      wsRef.current = null;
      startPolling(id);
    };

    ws.onclose = () => {
      wsRef.current = null;
      if (task?.status === 'running') {
        startPolling(id);
      }
    };
  }, [fetchTaskData, startPolling, task?.status]);

  // Simulate loading a running task for demo purposes
  const loadDemoTask = useCallback(() => {
    setLoading(true);
    // In real usage, user would select from task list or create one
    // For now, attempt to fetch from API; if it fails, show empty state
    setLoading(false);
  }, []);

  useEffect(() => {
    return () => {
      clearConnections();
    };
  }, [clearConnections]);

  // Auto-connect WebSocket when a running task is loaded
  useEffect(() => {
    if (task?.id && task.status === 'running') {
      connectWebSocket(task.id);
    }
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [task?.id, task?.status, connectWebSocket]);

  const handlePause = useCallback(async () => {
    if (!task) return;
    try {
      await pauseEvolution(task.id);
      await fetchTaskData(task.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to pause task');
    }
  }, [task, fetchTaskData]);

  const handleStop = useCallback(async () => {
    if (!task) return;
    try {
      await stopEvolution(task.id);
      clearConnections();
      await fetchTaskData(task.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop task');
    }
  }, [task, fetchTaskData, clearConnections]);

  const handleResume = useCallback(async () => {
    if (!task) return;
    try {
      // Resume is same as start evolution again with same config
      await pauseEvolution(task.id);
      await fetchTaskData(task.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resume task');
    }
  }, [task, fetchTaskData]);

  const handleRefresh = useCallback(() => {
    if (task) {
      void fetchTaskData(task.id);
    }
  }, [task, fetchTaskData]);

  // Empty state - no active task
  if (!task && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[70vh]">
        <Dna className="w-16 h-16 text-[var(--text-disabled)] mb-4" />
        <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
          Evolution Center
        </h2>
        <p className="text-[var(--text-secondary)] text-sm text-center max-w-md mb-6">
          Start an evolution task from the Strategy Lab to automatically optimize
          your trading strategies through genetic algorithms.
        </p>
        <Button variant="primary" size="md" onClick={loadDemoTask}>
          <RefreshCw className="w-4 h-4" />
          Load Tasks
        </Button>
      </div>
    );
  }

  const statusBadge = task ? getStatusBadge(task.status) : null;
  const population = task?.population ?? DEFAULT_POPULATION;
  const targetScore = task?.target_score ?? 80;
  const progress = task ? (task.current_generation / task.max_generations) * 100 : 0;

  return (
    <div className="h-full -m-6 flex flex-col overflow-hidden">
      {/* Task Info Bar */}
      <div className="bg-[var(--bg-card)] border-b border-[var(--border)] px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Dna className="w-5 h-5 text-[var(--color-purple)]" />
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                Evolution Task
              </h2>
            </div>

            {task && statusBadge && (
              <>
                <div className="h-4 w-px bg-[var(--border)]" />
                <span className="text-xs text-[var(--text-secondary)]">
                  {task.symbol} / {task.interval}
                </span>
                <div className="h-4 w-px bg-[var(--border)]" />
                <span className="text-xs text-[var(--text-secondary)]">
                  Gen {task.current_generation}/{task.max_generations}
                </span>
                <div className="h-4 w-px bg-[var(--border)]" />
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusBadge.className}`}>
                  {statusBadge.label}
                </span>
                <div className="h-4 w-px bg-[var(--border)]" />
                <span className="text-xs text-[var(--text-disabled)] flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatDuration(task.created_at)}
                </span>
              </>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={handleRefresh}>
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
            {task && task.status === 'running' && (
              <>
                <Button variant="secondary" size="sm" onClick={handlePause}>
                  <Pause className="w-3.5 h-3.5" />
                  Pause
                </Button>
                <Button variant="danger" size="sm" onClick={handleStop}>
                  <Square className="w-3.5 h-3.5" />
                  Stop
                </Button>
              </>
            )}
            {task && task.status === 'paused' && (
              <Button variant="primary" size="sm" onClick={handleResume}>
                <Play className="w-3.5 h-3.5" />
                Resume
              </Button>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        {task && (
          <div className="mt-2 h-1 bg-[var(--bg-primary)] rounded-full overflow-hidden">
            <div
              className="h-full bg-[var(--color-purple)] rounded-full transition-all duration-500"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
        )}
      </div>

      {error && (
        <div className="px-4 py-2 bg-[var(--color-loss)]/10 border-b border-[var(--color-loss)]/20">
          <p className="text-xs text-[var(--color-loss)]">{error}</p>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Generation Chart */}
        <GenerationChart data={history} targetScore={targetScore} />

        {/* Middle Row: Best Strategy + Mutation Log */}
        <div className="grid grid-cols-2 gap-4">
          {/* Best Strategy Card */}
          <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden">
            <div className="px-3 py-2 border-b border-[var(--border)] flex items-center gap-2">
              <Target className="w-3.5 h-3.5 text-[var(--color-profit)]" />
              <h3 className="text-sm font-medium text-[var(--text-primary)]">Current Best Strategy</h3>
            </div>
            {task?.best_strategy ? (
              <div className="p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-[var(--text-secondary)]">
                    From Generation {task.best_strategy.generation}
                  </span>
                  <span className="text-lg font-bold text-[var(--color-profit)]">
                    {task.best_strategy.total_score.toFixed(1)}
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-2">
                  {(
                    Object.entries(task.best_strategy.dimension_scores) as [string, number][]
                  ).map(([key, value]) => (
                    <div key={key} className="text-center">
                      <div className="text-xs text-[var(--text-disabled)] capitalize">
                        {key.replace('_', ' ')}
                      </div>
                      <div className={`text-sm font-medium ${
                        value >= 80 ? 'text-[var(--color-profit)]' :
                        value >= 60 ? 'text-[var(--color-blue)]' :
                        'text-[var(--color-warn)]'
                      }`}>
                        {value.toFixed(0)}
                      </div>
                    </div>
                  ))}
                </div>
                {task.best_strategy.signal_genes.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-xs text-[var(--text-disabled)]">Signals</span>
                    <div className="flex flex-wrap gap-1">
                      {task.best_strategy.signal_genes.slice(0, 4).map((gene) => (
                        <span
                          key={gene.id}
                          className="px-1.5 py-0.5 bg-[var(--bg-hover)] rounded text-[10px] text-[var(--text-secondary)]"
                        >
                          {gene.indicator} {gene.condition}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex gap-3 text-xs text-[var(--text-disabled)]">
                  <span>SL: {task.best_strategy.risk_genes.stop_loss}%</span>
                  <span>TP: {task.best_strategy.risk_genes.take_profit}%</span>
                  <span>Pos: {task.best_strategy.risk_genes.position_size}%</span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8">
                <TrendingUp className="w-8 h-8 text-[var(--text-disabled)] mb-2" />
                <p className="text-xs text-[var(--text-disabled)]">Waiting for first generation</p>
              </div>
            )}
          </div>

          {/* Mutation Log */}
          <MutationLog entries={mutationLogs} />
        </div>

        {/* Population Status */}
        <PopulationStatus population={population} />
      </div>
    </div>
  );
}
