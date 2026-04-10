import client from './client';
import type {
  Strategy,
  StrategyCreateRequest,
  StrategyListParams,
  StrategyListItem,
  PaginatedResponse,
  BacktestRequest,
  BacktestResponse,
  CompareResult,
  AppConfig,
} from '@/types';

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

export async function runBacktest(request: BacktestRequest): Promise<BacktestResponse> {
  const { data } = await client.post('/strategies/backtest', request);
  return data;
}

export async function listStrategies(
  params: StrategyListParams,
): Promise<PaginatedResponse<StrategyListItem>> {
  const { data } = await client.get('/strategies', { params });
  return data;
}

export async function compareStrategies(
  strategyIds: string[],
): Promise<CompareResult> {
  const { data } = await client.post('/strategies/compare', {
    strategy_ids: strategyIds,
  });
  return data;
}

export async function getConfig(): Promise<AppConfig> {
  const { data } = await client.get('/config');
  return data;
}

export async function updateConfig(config: Partial<AppConfig>): Promise<AppConfig> {
  const { data } = await client.put('/config', config);
  return data;
}
