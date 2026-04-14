import { useMutation } from "@tanstack/react-query";
import * as api from "@/services/validation";
import { toast } from "sonner";

export function useValidateHypothesis() {
  return useMutation({
    mutationFn: api.validateHypothesis,
    onSuccess: () => {
      toast.success("验证完成");
    },
    onError: (err) => toast.error(`验证失败: ${err.message}`),
  });
}
