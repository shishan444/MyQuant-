import client from './client';
import type { Strategy, StrategyCreateRequest, PaginatedResponse } from '@/types';

export async function getStrategies(page = 1, pageSize = 20): Promise<PaginatedResponse<Strategy>> {
  const { data } = await client.get('/strategies', {
    params: { page, page_size: pageSize },
  });
  return data;
}

export async function getStrategy(id: string): Promise<Strategy> {
  const { data } = await client.get(`/strategies/${id}`);
  return data;
}

export async function createStrategy(request: StrategyCreateRequest): Promise<Strategy> {
  const { data } = await client.post('/strategies', request);
  return data;
}

export async function deleteStrategy(id: string): Promise<void> {
  await client.delete(`/strategies/${id}`);
}

export async function updateStrategy(
  id: string,
  request: Partial<StrategyCreateRequest>,
): Promise<Strategy> {
  const { data } = await client.put(`/strategies/${id}`, request);
  return data;
}
