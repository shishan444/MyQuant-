/** Scene verification API service. */
import { api } from "./api";
import type {
  SceneTypeInfo,
  SceneVerifyRequest,
  SceneVerifyResponse,
} from "@/types/scene";

export async function getSceneTypes(): Promise<{ types: SceneTypeInfo[] }> {
  const { data } = await api.get("/api/scene/types");
  return data;
}

export async function verifyScene(
  payload: SceneVerifyRequest,
): Promise<SceneVerifyResponse> {
  const { data } = await api.post("/api/validate/scene", payload);
  return data;
}
