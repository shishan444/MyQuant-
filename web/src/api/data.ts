import client from './client';
import type { Dataset, DatasetPreview, CsvDetectResult, ImportResponse, ImportStrategy } from '@/types';

export async function getDatasets(): Promise<Dataset[]> {
  const { data } = await client.get('/data/datasets');
  return data;
}

export async function getDatasetPreview(id: string, rows = 5): Promise<DatasetPreview> {
  const { data } = await client.get(`/data/datasets/${id}/preview`, {
    params: { rows },
  });
  return data;
}

export async function deleteDataset(id: string): Promise<void> {
  await client.delete(`/data/datasets/${id}`);
}

export async function detectCsv(file: File): Promise<CsvDetectResult> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await client.post('/data/detect', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function importCsv(
  file: File,
  strategy: ImportStrategy,
  targetDatasetId?: string,
): Promise<ImportResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('strategy', strategy);
  if (targetDatasetId) {
    formData.append('target_dataset_id', targetDatasetId);
  }
  const { data } = await client.post('/data/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}
