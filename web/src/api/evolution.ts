import client from './client';
import type { EvolutionTask, PaginatedResponse } from '@/types';

export async function getEvolutionTasks(
  page = 1,
  pageSize = 20,
): Promise<PaginatedResponse<EvolutionTask>> {
  const { data } = await client.get('/evolution/tasks', {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function getEvolutionTask(id: string): Promise<EvolutionTask> {
  const { data } = await client.get(`/evolution/tasks/${id}`);
  return data;
}

export async function startEvolution(
  strategyId: string,
  config: {
    symbol: string;
    interval: string;
    start_date: string;
    end_date: string;
    max_generations: number;
  },
): Promise<EvolutionTask> {
  const { data } = await client.post('/evolution/start', {
    strategy_id: strategyId,
    ...config,
  });
  return data;
}

export async function stopEvolution(id: string): Promise<EvolutionTask> {
  const { data } = await client.post(`/evolution/tasks/${id}/stop`);
  return data;
}
