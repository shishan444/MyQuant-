import { api } from "./api";
import type { ValidateRequest, ValidateResponse, RuleValidateRequest, RuleValidateResponse } from "@/types/api";

export async function validateHypothesis(
  payload: ValidateRequest,
): Promise<ValidateResponse> {
  const { data } = await api.post("/api/validate", payload);
  return data;
}

export async function validateRules(
  payload: RuleValidateRequest,
): Promise<RuleValidateResponse> {
  const { data } = await api.post("/api/validate/rules", payload);
  return data;
}
