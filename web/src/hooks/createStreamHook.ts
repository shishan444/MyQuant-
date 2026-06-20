import { useState, useCallback, useRef } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { VerifyProgressEvent } from "@/services/strategies";

/** Shared streaming state for SSE-driven progressive operations. */
export interface StreamState {
  status: "idle" | "running" | "done" | "error";
  progress: { current: number; total: number };
  currentGroup: string;
  rangeLabel: string;
  results: unknown[];
  summary: unknown[];
  sessionId: string | null;
  error: string | null;
}

export interface StreamCallbacks<TComplete> {
  onProgress: (event: VerifyProgressEvent) => void;
  onComplete: (data: TComplete) => void;
  onError: (message: string) => void;
}

interface StreamHookConfig<TPayload, TComplete extends { summary: unknown[]; results: unknown[] }> {
  /** SSE stream driver, e.g. api.verifyStrategiesStream. */
  streamFn: (
    payload: TPayload,
    callbacks: StreamCallbacks<TComplete>,
    signal: AbortSignal,
  ) => void;
  /** Toast error prefix, e.g. "验证失败". */
  errorLabel: string;
  /** When set, the matching field of onComplete data is stored as sessionId. */
  sessionIdKey?: keyof TComplete;
  /** Extra side effect on completion, e.g. invalidate queries. */
  onCompleteExtra?: (qc: QueryClient) => void;
}

const initialState = (): StreamState => ({
  status: "idle",
  progress: { current: 0, total: 0 },
  currentGroup: "",
  rangeLabel: "",
  results: [],
  summary: [],
  sessionId: null,
  error: null,
});

/**
 * Factory that eliminates the per-hook boilerplate (state shape + start/cancel/reset
 * + AbortController + toast) shared by useVerifyStream and useBatchBacktestStream.
 * Behaviour is identical to the previous hand-written hooks; only the four real
 * differences (streamFn / errorLabel / sessionId / onComplete invalidate) are parameterised.
 */
export function createStreamHook<TPayload, TComplete extends { summary: unknown[]; results: unknown[] }>(
  config: StreamHookConfig<TPayload, TComplete>,
) {
  return function useStream() {
    const qc = useQueryClient();
    const abortRef = useRef<AbortController | null>(null);
    const cancelledRef = useRef(false);
    const [state, setState] = useState<StreamState>(initialState);

    const start = useCallback(
      (payload: TPayload) => {
        const ac = new AbortController();
        abortRef.current = ac;
        cancelledRef.current = false;
        setState({ ...initialState(), status: "running" });

        const callbacks: StreamCallbacks<TComplete> = {
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
            const sessionId = config.sessionIdKey
              ? (data[config.sessionIdKey] as unknown as string)
              : null;
            setState((s) => ({
              ...s,
              status: "done",
              summary: data.summary,
              results: data.results,
              sessionId,
            }));
            config.onCompleteExtra?.(qc);
          },
          onError: (message) => {
            if (cancelledRef.current) return;
            setState((s) => ({ ...s, status: "error", error: message }));
            toast.error(`${config.errorLabel}: ${message}`, { duration: Infinity });
          },
        };

        config.streamFn(payload, callbacks, ac.signal);
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
      setState(initialState());
    }, []);

    return { ...state, start, cancel, reset };
  };
}
