import { api } from "./api";
import type {
  EvolutionTask,
  EvolutionTaskListResponse,
  EvolutionHistoryResponse,
  EvolvedStrategy,
} from "@/types/api";

export async function getEvolutionTasks(params?: {
  status?: string;
  limit?: number;
  offset?: number;
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
  return data;
}

export async function getTaskStrategies(taskId: string): Promise<{
  task_id: string;
  strategies: EvolvedStrategy[];
}> {
  const { data } = await api.get(`/api/evolution/tasks/${taskId}/strategies`);
  return data;
}
