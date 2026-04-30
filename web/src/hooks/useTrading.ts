import {
  useQuery,
  useMutation,
  useQueryClient,
  queryOptions,
} from "@tanstack/react-query";
import { useEffect, useRef, useCallback } from "react";
import {
  listTradingTasks,
  getTradingTask,
  createTradingTask,
  stopTradingTask,
  pauseTradingTask,
  resumeTradingTask,
  getTradingTrades,
  type CreateTradingTaskParams,
  type TradingTask,
} from "@/services/trading";

// -- Query key factory --

const tradingKeys = {
  all: ["trading"] as const,
  tasks: () => [...tradingKeys.all, "tasks"] as const,
  task: (id: string) => [...tradingKeys.all, "task", id] as const,
  trades: (id: string) => [...tradingKeys.all, "trades", id] as const,
};

// -- Query options --

export function tradingTasksOptions() {
  return queryOptions({
    queryKey: tradingKeys.tasks(),
    queryFn: () => listTradingTasks(),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.tasks.some((t) => t.status === "running" || t.status === "pending")) {
        return 5000;
      }
      return false;
    },
  });
}

export function tradingTaskOptions(taskId: string) {
  return queryOptions({
    queryKey: tradingKeys.task(taskId),
    queryFn: () => getTradingTask(taskId),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "pending" ? 3000 : false;
    },
  });
}

export function tradingTradesOptions(taskId: string, limit = 50) {
  return queryOptions({
    queryKey: tradingKeys.trades(taskId),
    queryFn: () => getTradingTrades(taskId, limit),
    enabled: !!taskId,
  });
}

// -- Hooks --

export function useTradingTasks() {
  return useQuery(tradingTasksOptions());
}

export function useTradingTask(taskId: string) {
  return useQuery(tradingTaskOptions(taskId));
}

export function useTradingTrades(taskId: string, limit?: number) {
  return useQuery(tradingTradesOptions(taskId, limit));
}

export function useCreateTradingTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: CreateTradingTaskParams) => createTradingTask(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: tradingKeys.tasks() });
    },
  });
}

export function useStopTradingTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => stopTradingTask(taskId),
    onSuccess: (_data, taskId) => {
      qc.invalidateQueries({ queryKey: tradingKeys.task(taskId) });
      qc.invalidateQueries({ queryKey: tradingKeys.tasks() });
    },
  });
}

export function usePauseTradingTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => pauseTradingTask(taskId),
    onSuccess: (_data, taskId) => {
      qc.invalidateQueries({ queryKey: tradingKeys.task(taskId) });
      qc.invalidateQueries({ queryKey: tradingKeys.tasks() });
    },
  });
}

export function useResumeTradingTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => resumeTradingTask(taskId),
    onSuccess: (_data, taskId) => {
      qc.invalidateQueries({ queryKey: tradingKeys.task(taskId) });
      qc.invalidateQueries({ queryKey: tradingKeys.tasks() });
    },
  });
}

// -- WebSocket --

export function useTradingWebSocket(taskId: string | null) {
  const qc = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const scheduleInvalidation = useCallback(() => {
    clearTimeout(reconnectTimer.current);
    reconnectTimer.current = setTimeout(() => {
      qc.invalidateQueries({ queryKey: tradingKeys.tasks() });
      if (taskId) {
        qc.invalidateQueries({ queryKey: tradingKeys.task(taskId) });
        qc.invalidateQueries({ queryKey: tradingKeys.trades(taskId) });
      }
    }, 2000);
  }, [qc, taskId]);

  useEffect(() => {
    if (!taskId) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = import.meta.env.VITE_WS_URL
      ? new URL(import.meta.env.VITE_WS_URL).host
      : window.location.host;
    const wsUrl = `${protocol}//${host}/ws/trading/${taskId}`;

    const connect = () => {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "position_update" || msg.type === "task_started") {
            scheduleInvalidation();
          }
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        reconnectTimer.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      wsRef.current?.close();
      wsRef.current = null;
      clearTimeout(reconnectTimer.current);
    };
  }, [taskId, scheduleInvalidation]);
}
