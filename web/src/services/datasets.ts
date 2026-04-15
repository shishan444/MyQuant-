import { api } from "./api";
import type {
  AvailableSourcesResponse,
  ChartIndicatorsResponse,
  Dataset,
  DatasetListResponse,
  OhlcvData,
} from "@/types/api";

export async function getDatasets(
  params?: { symbol?: string; interval?: string }
): Promise<DatasetListResponse> {
  const { data } = await api.get("/api/data/datasets", { params });
  return data;
}

export async function getDataset(id: string): Promise<Dataset> {
  const { data } = await api.get(`/api/data/datasets/${id}`);
  return data;
}

export async function importCsv(formData: FormData): Promise<{
  dataset_id: string;
  symbol: string;
  interval: string;
  rows_imported: number;
}> {
  const { data } = await api.post("/api/data/import", formData, {
    timeout: 120000,
  });
  return data;
}

export async function importCsvBatch(formData: FormData): Promise<{
  dataset_id: string;
  symbol: string;
  interval: string;
  rows_imported: number;
  files_processed: number;
}> {
  const { data } = await api.post("/api/data/import-batch", formData, {
    timeout: 300000,
  });
  return data;
}

export async function deleteDataset(id: string): Promise<void> {
  await api.delete(`/api/data/datasets/${id}`);
}

export async function getOhlcv(
  id: string,
  params?: { start?: string; end?: string; limit?: number }
): Promise<OhlcvData> {
  const { data } = await api.get(`/api/data/datasets/${id}/ohlcv`, { params });
  return data;
}

export async function getDatasetPreview(
  id: string,
  params?: { rows?: number }
): Promise<{ rows: Record<string, unknown>[]; columns: string[] }> {
  const { data } = await api.get(`/api/data/datasets/${id}/preview`, { params });
  return data;
}

export async function getAvailableSources(): Promise<AvailableSourcesResponse> {
  const { data } = await api.get("/api/data/available-sources");
  return data;
}

export async function getOhlcvBySymbol(
  symbol: string,
  timeframe: string,
  params?: { start?: string; end?: string; limit?: number }
): Promise<OhlcvData> {
  const { data } = await api.get(`/api/data/ohlcv/${symbol}/${timeframe}`, { params });
  return data;
}

export async function getChartIndicators(
  symbol: string,
  timeframe: string,
  params?: {
    start?: string;
    end?: string;
    ema_periods?: string;
    boll_enabled?: boolean;
    boll_period?: number;
    boll_std?: number;
    rsi_enabled?: boolean;
    rsi_period?: number;
  }
): Promise<ChartIndicatorsResponse> {
  const { data } = await api.get(`/api/data/chart-indicators/${symbol}/${timeframe}`, { params });
  return data;
}
