import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/services/datasets";
import { toast } from "sonner";

export const datasetsKeys = {
  all: ["datasets"] as const,
  list: (filters?: Record<string, string>) =>
    ["datasets", "list", filters] as const,
  detail: (id: string) => ["datasets", "detail", id] as const,
  ohlcv: (id: string, params?: Record<string, string>) =>
    ["datasets", id, "ohlcv", params] as const,
};

export function useDatasets(filters?: { symbol?: string; interval?: string }) {
  return queryOptions({
    queryKey: datasetsKeys.list(filters),
    queryFn: () => api.getDatasets(filters),
  });
}

export function useDataset(id: string) {
  return queryOptions({
    queryKey: datasetsKeys.detail(id),
    queryFn: () => api.getDataset(id),
    enabled: !!id,
  });
}

export function useOhlcv(
  id: string,
  params?: { start?: string; end?: string; limit?: number }
) {
  return queryOptions({
    queryKey: datasetsKeys.ohlcv(id, params as Record<string, string>),
    queryFn: () => api.getOhlcv(id, params),
    enabled: !!id,
  });
}

export function useImportCsv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.importCsv,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: datasetsKeys.all });
      toast.success("数据导入成功");
    },
    onError: (err) => toast.error(`导入失败: ${err.message}`),
  });
}

export function useImportCsvBatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.importCsvBatch,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: datasetsKeys.all });
      toast.success("批量导入成功");
    },
    onError: (err) => toast.error(`批量导入失败: ${err.message}`),
  });
}

export function useDeleteDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteDataset,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: datasetsKeys.all });
      toast.success("数据集已删除");
    },
    onError: (err) => toast.error(`删除失败: ${err.message}`),
  });
}
