import { useState, useCallback, useRef } from "react";
import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/services/strategies";
import type { VerifyProgressEvent, VerifyStreamCallbacks } from "@/services/strategies";
import { toast } from "sonner";

export const strategiesKeys = {
  all: ["strategies"] as const,
  list: (filters?: Record<string, string>) =>
    ["strategies", "list", filters] as const,
  detail: (id: string) => ["strategies", "detail", id] as const,
};

export function useStrategies(filters?: {
  symbol?: string;
  source?: string;
  tags?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  limit?: number;
}) {
  return queryOptions({
    queryKey: strategiesKeys.list(filters as Record<string, string>),
    queryFn: () => api.getStrategies(filters),
  });
}

export function useStrategy(id: string) {
  return queryOptions({
    queryKey: strategiesKeys.detail(id),
    queryFn: () => api.getStrategy(id),
    enabled: !!id,
  });
}

export function useRunBacktest() {
  return useMutation({
    mutationFn: api.runBacktest,
    onSuccess: () => toast.success("回测完成"),
    onError: (err) => toast.error(`回测失败: ${err.message}`, { duration: Infinity }),
  });
}

export function useCreateStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createStrategy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strategiesKeys.all });
      toast.success("策略已保存");
    },
    onError: (err) => toast.error(`保存失败: ${err.message}`),
  });
}

export function useDeleteStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteStrategy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strategiesKeys.all });
      toast.success("策略已删除");
    },
    onError: (err) => toast.error(`删除失败: ${err.message}`),
  });
}

export function useUpdateStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof api.updateStrategy>[1] }) =>
      api.updateStrategy(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strategiesKeys.all });
      toast.success("策略已更新");
    },
    onError: (err) => toast.error(`更新失败: ${err.message}`),
  });
}

export function useVerifyStrategies() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.verifyStrategies,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [...strategiesKeys.all, "verify-sessions"] });
      toast.success("验证完成");
    },
    onError: (err) => toast.error(`验证失败: ${err.message}`, { duration: Infinity }),
  });
}

export interface VerifyStreamState {
  status: "idle" | "running" | "done" | "error";
  progress: { current: number; total: number };
  currentGroup: string;
  rangeLabel: string;
  results: unknown[];
  summary: unknown[];
  sessionId: string | null;
  error: string | null;
}

export function useVerifyStream() {
  const qc = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);
  const cancelledRef = useRef(false);

  const [state, setState] = useState<VerifyStreamState>({
    status: "idle",
    progress: { current: 0, total: 0 },
    currentGroup: "",
    rangeLabel: "",
    results: [],
    summary: [],
    sessionId: null,
    error: null,
  });

  const start = useCallback(
    (payload: {
      strategy_ids: string[];
      data_ranges: Array<{ start: string; end: string }>;
      init_cash?: number;
      fee?: number;
      slippage?: number;
      leverage?: number;
    }) => {
      const ac = new AbortController();
      abortRef.current = ac;
      cancelledRef.current = false;

      setState((s) => ({
        ...s,
        status: "running",
        progress: { current: 0, total: 0 },
        currentGroup: "",
        rangeLabel: "",
        results: [],
        summary: [],
        sessionId: null,
        error: null,
      }));

      const callbacks: VerifyStreamCallbacks = {
        onProgress: (event: VerifyProgressEvent) => {
          if (cancelledRef.current) return;
          setState((s) => ({
            ...s,
            progress: { current: event.current, total: event.total },
            currentGroup: event.group,
            rangeLabel: `${event.range_start} ~ ${event.range_end}`,
            results: [...s.results, ...event.batch_results],
          }));
        },
        onComplete: (data) => {
          if (cancelledRef.current) return;
          setState((s) => ({
            ...s,
            status: "done",
            summary: data.summary,
            results: data.results,
            sessionId: data.session_id,
          }));
          qc.invalidateQueries({ queryKey: [...strategiesKeys.all, "verify-sessions"] });
        },
        onError: (message) => {
          if (cancelledRef.current) return;
          setState((s) => ({ ...s, status: "error", error: message }));
          toast.error(`验证失败: ${message}`, { duration: Infinity });
        },
      };

      api.verifyStrategiesStream(payload, callbacks, ac.signal);
    },
    [qc],
  );

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    abortRef.current?.abort();
    setState((s) => ({ ...s, status: "idle" }));
  }, []);

  const reset = useCallback(() => {
    cancelledRef.current = false;
    setState({
      status: "idle",
      progress: { current: 0, total: 0 },
      currentGroup: "",
      rangeLabel: "",
      results: [],
      summary: [],
      sessionId: null,
      error: null,
    });
  }, []);

  return { ...state, start, cancel, reset };
}

export interface BatchBacktestStreamState {
  status: "idle" | "running" | "done" | "error";
  progress: { current: number; total: number };
  currentGroup: string;
  rangeLabel: string;
  results: unknown[];
  summary: unknown[];
  error: string | null;
}

export function useBatchBacktestStream() {
  const abortRef = useRef<AbortController | null>(null);
  const cancelledRef = useRef(false);

  const [state, setState] = useState<BatchBacktestStreamState>({
    status: "idle",
    progress: { current: 0, total: 0 },
    currentGroup: "",
    rangeLabel: "",
    results: [],
    summary: [],
    error: null,
  });

  const start = useCallback(
    (payload: {
      strategy_ids: string[];
      data_ranges: Array<{ start: string; end: string }>;
      init_cash?: number;
      fee?: number;
      slippage?: number;
      leverage?: number;
    }) => {
      const ac = new AbortController();
      abortRef.current = ac;
      cancelledRef.current = false;

      setState((s) => ({
        ...s,
        status: "running",
        progress: { current: 0, total: 0 },
        currentGroup: "",
        rangeLabel: "",
        results: [],
        summary: [],
        error: null,
      }));

      const callbacks: import("@/services/strategies").BatchBacktestStreamCallbacks = {
        onProgress: (event) => {
          if (cancelledRef.current) return;
          setState((s) => ({
            ...s,
            progress: { current: event.current, total: event.total },
            currentGroup: event.group,
            rangeLabel: `${event.range_start} ~ ${event.range_end}`,
            results: [...s.results, ...event.batch_results],
          }));
        },
        onComplete: (data) => {
          if (cancelledRef.current) return;
          setState((s) => ({
            ...s,
            status: "done",
            summary: data.summary,
            results: data.results,
          }));
        },
        onError: (message) => {
          if (cancelledRef.current) return;
          setState((s) => ({ ...s, status: "error", error: message }));
          toast.error(`批量回测失败: ${message}`, { duration: Infinity });
        },
      };

      api.batchBacktestStream(payload, callbacks, ac.signal);
    },
    [],
  );

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    abortRef.current?.abort();
    setState((s) => ({ ...s, status: "idle" }));
  }, []);

  const reset = useCallback(() => {
    cancelledRef.current = false;
    setState({
      status: "idle",
      progress: { current: 0, total: 0 },
      currentGroup: "",
      rangeLabel: "",
      results: [],
      summary: [],
      error: null,
    });
  }, []);

  return { ...state, start, cancel, reset };
}

export function useVerifyHistory(strategyId?: string) {
  return queryOptions({
    queryKey: [...strategiesKeys.all, "verify-history", strategyId],
    queryFn: () => api.getVerifyHistory({ strategy_id: strategyId, limit: 500 }),
  });
}

export function useVerifySessions() {
  return queryOptions({
    queryKey: [...strategiesKeys.all, "verify-sessions"],
    queryFn: () => api.getVerifySessions(50),
  });
}

export function useSessionResults(sessionId: string | null) {
  return queryOptions({
    queryKey: [...strategiesKeys.all, "session-results", sessionId],
    queryFn: () => api.getSessionResults(sessionId!),
    enabled: !!sessionId,
  });
}
