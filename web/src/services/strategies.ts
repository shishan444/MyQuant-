import { api } from "./api";
import type {
  Strategy,
  StrategyListResponse,
  BacktestResult,
} from "@/types/api";

export async function getStrategies(params?: {
  symbol?: string;
  source?: string;
  tags?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}): Promise<StrategyListResponse> {
  const { data } = await api.get("/api/strategies", { params });
  return data;
}

export async function getStrategy(id: string): Promise<Strategy> {
  const { data } = await api.get(`/api/strategies/${id}`);
  return data;
}

export async function createStrategy(payload: {
  name?: string;
  dna: unknown;
  symbol: string;
  timeframe: string;
  source: string;
  source_task_id?: string;
  tags?: string;
  notes?: string;
}): Promise<Strategy> {
  const { data } = await api.post("/api/strategies", payload);
  return data;
}

export async function updateStrategy(
  id: string,
  payload: Partial<{ name: string; tags: string; notes: string }>
): Promise<Strategy> {
  const { data } = await api.put(`/api/strategies/${id}`, payload);
  return data;
}

export async function deleteStrategy(id: string): Promise<void> {
  await api.delete(`/api/strategies/${id}`);
}

export async function runBacktest(payload: {
  dna: unknown;
  symbol: string;
  timeframe: string;
  dataset_id?: string;
  score_template?: string;
  init_cash?: number;
  fee?: number;
  slippage?: number;
  data_start?: string;
  data_end?: string;
  timeframe_pool?: string[];
}): Promise<BacktestResult> {
  const { data } = await api.post("/api/strategies/backtest", payload, {
    timeout: 60000,
  });
  return data;
}

export async function compareStrategies(payload: {
  strategy_ids: string[];
  dataset_id?: string;
  score_template?: string;
}): Promise<{ results: BacktestResult[] }> {
  const { data } = await api.post("/api/strategies/compare", payload);
  return data;
}
