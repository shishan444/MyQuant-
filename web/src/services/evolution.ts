import { api } from "./api";
import type {
  EvolutionTask,
  EvolutionTaskListResponse,
  EvolutionHistoryResponse,
  EvolvedStrategy,
  DiscoveredStrategy,
} from "@/types/api";

export async function getEvolutionTasks(params?: {
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<EvolutionTaskListResponse> {
  const { data } = await api.get("/api/evolution/tasks", { params });
  return data;
}

export async function getEvolutionTask(id: string): Promise<EvolutionTask> {
  const { data } = await api.get(`/api/evolution/tasks/${id}`);
  return data;
}

export async function createEvolutionTask(payload: {
  initial_dna?: unknown;
  symbol: string;
  timeframe: string;
  target_score?: number;
  score_template?: string;
  population_size?: number;
  max_generations?: number;
  indicator_pool?: string[];
  timeframe_pool?: string[];
  mode?: "auto" | "seed";
  leverage?: number;
  direction?: "long" | "short" | "mixed";
  data_start?: string;
  data_end?: string;
  walk_forward_enabled?: boolean;
  strategy_threshold?: number;
}): Promise<EvolutionTask> {
  const { data } = await api.post("/api/evolution/tasks", payload);
  return data;
}

export async function pauseEvolutionTask(id: string): Promise<EvolutionTask> {
  const { data } = await api.post(`/api/evolution/tasks/${id}/pause`);
  return data;
}

export async function stopEvolutionTask(id: string): Promise<EvolutionTask> {
  const { data } = await api.post(`/api/evolution/tasks/${id}/stop`);
  return data;
}

export async function resumeEvolutionTask(id: string): Promise<EvolutionTask> {
  const { data } = await api.post(`/api/evolution/tasks/${id}/resume`);
  return data;
}

export async function getEvolutionHistory(
  id: string,
  params?: { limit?: number; offset?: number }
): Promise<EvolutionHistoryResponse> {
  const { data } = await api.get(`/api/evolution/tasks/${id}/history`, { params });
  // Backend returns { task_id, generations }, frontend expects { records, total }
  const generations = data.generations ?? data.records ?? [];
  return {
    records: generations,
    total: generations.length,
  };
}

export async function getTaskStrategies(taskId: string): Promise<{
  task_id: string;
  strategies: EvolvedStrategy[];
}> {
  const { data } = await api.get(`/api/evolution/tasks/${taskId}/strategies`);
  return data;
}

export async function getDiscoveredStrategies(
  taskId: string,
  params?: { min_score?: number; limit?: number }
): Promise<DiscoveredStrategy[]> {
  const { data } = await api.get(`/api/evolution/tasks/${taskId}/discovered-strategies`, { params });
  return data;
}

export async function getAllDiscoveredStrategies(
  params?: { min_score?: number; limit?: number }
): Promise<DiscoveredStrategy[]> {
  const { data } = await api.get("/api/evolution/strategies", { params });
  return data;
}
