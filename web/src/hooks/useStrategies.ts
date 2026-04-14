import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/services/strategies";
import { toast } from "sonner";

export const strategiesKeys = {
  all: ["strategies"] as const,
  list: (filters?: Record<string, string>) =>
    ["strategies", "list", filters] as const,
  detail: (id: string) => ["strategies", "detail", id] as const,
};

export function useStrategies(filters?: {
  symbol?: string;
  source?: string;
  tags?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  limit?: number;
}) {
  return queryOptions({
    queryKey: strategiesKeys.list(filters as Record<string, string>),
    queryFn: () => api.getStrategies(filters),
  });
}

export function useStrategy(id: string) {
  return queryOptions({
    queryKey: strategiesKeys.detail(id),
    queryFn: () => api.getStrategy(id),
    enabled: !!id,
  });
}

export function useRunBacktest() {
  return useMutation({
    mutationFn: api.runBacktest,
    onSuccess: () => toast.success("回测完成"),
    onError: (err) => toast.error(`回测失败: ${err.message}`, { duration: Infinity }),
  });
}

export function useCreateStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createStrategy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strategiesKeys.all });
      toast.success("策略已保存");
    },
    onError: (err) => toast.error(`保存失败: ${err.message}`),
  });
}

export function useDeleteStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteStrategy,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: strategiesKeys.all });
      toast.success("策略已删除");
    },
    onError: (err) => toast.error(`删除失败: ${err.message}`),
  });
}
