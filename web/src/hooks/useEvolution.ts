import { useEffect, useRef } from "react";
import {
  queryOptions,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import * as api from "@/services/evolution";
import { toast } from "sonner";
import type { EvolutionTask, EvolutionHistoryRecord, GenerationUpdate } from "@/types/api";
import { isActiveStatus } from "@/lib/constants";

export const evolutionKeys = {
  all: ["evolution"] as const,
  tasks: (filters?: Record<string, string>) =>
    ["evolution", "tasks", filters] as const,
  task: (id: string) => ["evolution", "task", id] as const,
  history: (id: string) => ["evolution", "history", id] as const,
  discovered: (id: string) => ["evolution", "discovered", id] as const,
};

export function useEvolutionTasks(filters?: {
  status?: string;
  limit?: number;
}) {
  return queryOptions({
    queryKey: evolutionKeys.tasks(filters as Record<string, string>),
    queryFn: () => api.getEvolutionTasks(filters),
    refetchInterval: (query) => {
      const items = (query.state.data as { items: EvolutionTask[] } | undefined)?.items;
      if (!items) return false;
      return items.some((t) => isActiveStatus(t.status)) ? 10000 : false;
    },
    refetchIntervalInBackground: true,
  });
}

export function useEvolutionTask(id: string) {
  return queryOptions({
    queryKey: evolutionKeys.task(id),
    queryFn: () => api.getEvolutionTask(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as EvolutionTask | undefined;
      if (!data) return false;
      return isActiveStatus(data.status) ? 5000 : false;
    },
    refetchIntervalInBackground: true,
  });
}

export function useEvolutionHistory(id: string, isActive?: boolean) {
  return queryOptions({
    queryKey: evolutionKeys.history(id),
    queryFn: () => api.getEvolutionHistory(id),
    enabled: !!id,
    refetchInterval: isActive ? 3000 : false,
    refetchIntervalInBackground: true,
  });
}

export function useDiscoveredStrategies(taskId?: string, minScore?: number) {
  return queryOptions({
    queryKey: [...evolutionKeys.discovered(taskId ?? ""), minScore],
    queryFn: () =>
      taskId
        ? api.getDiscoveredStrategies(taskId, { min_score: minScore, limit: 50 })
        : api.getAllDiscoveredStrategies({ min_score: minScore, limit: 20 }),
    enabled: !!taskId,
  });
}

export function useCreateEvolutionTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createEvolutionTask,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["evolution", "tasks"] });
      toast.success("进化任务已创建");
    },
    onError: (err) => toast.error(`创建失败: ${err.message}`),
  });
}

export function useStopEvolutionTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.stopEvolutionTask,
    onSuccess: (_data, taskId) => {
      qc.invalidateQueries({ queryKey: ["evolution", "tasks"] });
      qc.invalidateQueries({ queryKey: evolutionKeys.task(taskId) });
      toast.success("任务已停止");
    },
    onError: (err) => toast.error(`操作失败: ${err.message}`),
  });
}

export function usePauseEvolutionTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.pauseEvolutionTask,
    onSuccess: (_data, taskId) => {
      qc.invalidateQueries({ queryKey: ["evolution", "tasks"] });
      qc.invalidateQueries({ queryKey: evolutionKeys.task(taskId) });
      toast.success("任务已暂停", { description: "可以随时恢复" });
    },
    onError: (err) => toast.error(`操作失败: ${err.message}`),
  });
}

export function useResumeEvolutionTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.resumeEvolutionTask,
    onSuccess: (_data, taskId) => {
      qc.invalidateQueries({ queryKey: ["evolution", "tasks"] });
      qc.invalidateQueries({ queryKey: evolutionKeys.task(taskId) });
      toast.success("任务已恢复");
    },
    onError: (err) => toast.error(`操作失败: ${err.message}`),
  });
}

export function useEvolutionWebSocket(taskId: string | null) {
  const qc = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!taskId) return;

    const currentTaskId = taskId;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = import.meta.env.VITE_WS_URL
      ? new URL(import.meta.env.VITE_WS_URL).host
      : window.location.host;
    const wsUrl = `${protocol}//${host}/ws/evolution/${currentTaskId}`;

    let reconnectTimer: ReturnType<typeof setTimeout>;
    let invalidateTimer: ReturnType<typeof setTimeout> | null = null;
    let mounted = true;

    function scheduleInvalidation() {
      if (invalidateTimer) clearTimeout(invalidateTimer);
      invalidateTimer = setTimeout(() => {
        invalidateTimer = null;
        if (!mounted) return;
        qc.invalidateQueries({
          queryKey: evolutionKeys.history(currentTaskId),
        });
      }, 2000);
    }

    function connect() {
      if (!mounted) return;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const update: GenerationUpdate = JSON.parse(event.data);

          // Handle task_started: runner has begun execution
          if (update.type === "task_started") {
            qc.invalidateQueries({ queryKey: evolutionKeys.task(currentTaskId) });
            qc.invalidateQueries({ queryKey: ["evolution", "tasks"] });
            return;
          }

          // Handle task_snapshot: progress recovery on WS reconnect
          if (update.type === "task_snapshot") {
            qc.setQueryData(
              evolutionKeys.task(currentTaskId),
              (old: unknown) => {
                if (!old) {
                  qc.invalidateQueries({ queryKey: evolutionKeys.task(currentTaskId) });
                  return old;
                }
                const prev = old as Record<string, unknown>;
                return {
                  ...prev,
                  ...(update.current_generation != null ? { current_generation: update.current_generation } : {}),
                  ...(update.best_score != null ? { best_score: update.best_score } : {}),
                  ...(update.current_phase != null ? { current_phase: update.current_phase } : {}),
                  status: update.status ?? prev.status,
                };
              }
            );
            return;
          }

          // Handle phase_changed: runner phase transition
          if (update.type === "phase_changed") {
            qc.setQueryData(
              evolutionKeys.task(currentTaskId),
              (old: unknown) => {
                if (!old) return old;
                const prev = old as Record<string, unknown>;
                return { ...prev, current_phase: update.phase };
              }
            );
            return;
          }

          if (update.type === "population_started") {
            qc.setQueryData(
              evolutionKeys.task(currentTaskId),
              (old: unknown) => {
                if (!old) return old;
                const prev = old as Record<string, unknown>;
                return {
                  ...prev,
                  population_count: update.population_count,
                };
              }
            );
          } else if (update.type === "strategy_discovered") {
            // Invalidate per-task discovered strategies
            qc.invalidateQueries({
              queryKey: evolutionKeys.discovered(currentTaskId),
            });
            qc.invalidateQueries({
              queryKey: ["evolution", "tasks"],
            });
          } else if (
            update.type === "generation_complete" ||
            update.type === "evolution_complete"
          ) {
            qc.setQueryData(
              evolutionKeys.task(currentTaskId),
              (old: unknown) => {
                if (!old) {
                  // Cache not ready yet -- trigger refetch as fallback
                  qc.invalidateQueries({ queryKey: evolutionKeys.task(currentTaskId) });
                  return old;
                }
                const prev = old as Record<string, unknown>;
                return {
                  ...prev,
                  ...(update.generation != null ? { current_generation: update.generation } : {}),
                  ...(update.best_score != null ? { best_score: update.best_score } : {}),
                  champion_dna: update.champion_dna ?? prev.champion_dna,
                  status:
                    update.type === "evolution_complete"
                      ? "completed"
                      : prev.status,
                  ...(update.target_score != null ? { target_score: update.target_score } : {}),
                  ...(update.max_generations != null ? { max_generations: update.max_generations } : {}),
                };
              }
            );

            // Directly merge history record into cache for instant chart update
            if (update.type === "generation_complete" && update.generation != null) {
              qc.setQueryData(
                evolutionKeys.history(currentTaskId),
                (old: unknown) => {
                  if (!old) return old;
                  const prev = old as { records: EvolutionHistoryRecord[] };
                  const newRecord: EvolutionHistoryRecord = {
                    generation: update.generation,
                    best_score: update.best_score ?? 0,
                    avg_score: update.avg_score ?? 0,
                    created_at: new Date().toISOString(),
                  };
                  const records = prev.records ?? [];
                  // Avoid duplicate if this generation already exists
                  if (records.some((r) => r.generation === newRecord.generation)) return old;
                  return { ...prev, records: [...records, newRecord] };
                }
              );
            }
          } else {
            qc.setQueryData(
              evolutionKeys.task(currentTaskId),
              (old: unknown) => {
                if (!old) return old;
                return { ...(old as Record<string, unknown>), ...update };
              }
            );
          }

          scheduleInvalidation();
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        if (!mounted) return;
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      mounted = false;
      clearTimeout(reconnectTimer);
      if (invalidateTimer) clearTimeout(invalidateTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [taskId, qc]);
}
