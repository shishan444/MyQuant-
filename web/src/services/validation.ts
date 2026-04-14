import { api } from "./api";
import type { ValidateRequest, ValidateResponse } from "@/types/api";

export async function validateHypothesis(
  payload: ValidateRequest,
): Promise<ValidateResponse> {
  const { data } = await api.post("/api/validate", payload);
  return data;
}
