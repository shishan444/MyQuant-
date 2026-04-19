import { useEffect, useRef } from "react";
import {
  queryOptions,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import * as api from "@/services/evolution";
import { toast } from "sonner";
import type { GenerationUpdate } from "@/types/api";

export const evolutionKeys = {
  all: ["evolution"] as const,
  tasks: (filters?: Record<string, string>) =>
    ["evolution", "tasks", filters] as const,
  task: (id: string) => ["evolution", "task", id] as const,
  history: (id: string) => ["evolution", "history", id] as const,
  strategies: (id: string) => ["evolution", "strategies", id] as const,
};

export function useEvolutionTasks(filters?: {
  status?: string;
  limit?: number;
}) {
  return queryOptions({
    queryKey: evolutionKeys.tasks(filters as Record<string, string>),
    queryFn: () => api.getEvolutionTasks(filters),
  });
}

export function useEvolutionTask(id: string) {
  return queryOptions({
    queryKey: evolutionKeys.task(id),
    queryFn: () => api.getEvolutionTask(id),
    enabled: !!id,
  });
}

export function useEvolutionHistory(id: string) {
  return queryOptions({
    queryKey: evolutionKeys.history(id),
    queryFn: () => api.getEvolutionHistory(id),
    enabled: !!id,
  });
}

export function useEvolutionStrategies(taskId: string) {
  return queryOptions({
    queryKey: evolutionKeys.strategies(taskId),
    queryFn: () => api.getTaskStrategies(taskId),
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
      if (invalidateTimer) return;
      invalidateTimer = setTimeout(() => {
        invalidateTimer = null;
        if (!mounted) return;
        qc.invalidateQueries({
          queryKey: evolutionKeys.history(currentTaskId),
        });
        qc.invalidateQueries({
          queryKey: evolutionKeys.strategies(currentTaskId),
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
          } else if (
            update.type === "generation_complete" ||
            update.type === "evolution_complete"
          ) {
            qc.setQueryData(
              evolutionKeys.task(currentTaskId),
              (old: unknown) => {
                if (!old) return old;
                const prev = old as Record<string, unknown>;
                return {
                  ...prev,
                  current_generation: update.generation,
                  best_score: update.best_score,
                  champion_dna: update.champion_dna ?? prev.champion_dna,
                  status:
                    update.type === "evolution_complete"
                      ? "completed"
                      : prev.status,
                  target_score: update.target_score,
                  max_generations: update.max_generations,
                };
              }
            );
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
