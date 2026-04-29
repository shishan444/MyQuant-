import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 30000,
  transformRequest: [
    (data, headers) => {
      if (data instanceof FormData) {
        delete headers["Content-Type"];
        return data;
      }
      if (typeof data === "object" && data !== null) {
        headers["Content-Type"] = "application/json";
        return JSON.stringify(data);
      }
      return data;
    },
  ],
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail;
    let message: string;
    if (Array.isArray(detail)) {
      // Pydantic 422 validation errors: [{loc: [...], msg: "..."}, ...]
      message = detail
        .map((e: { loc?: string[]; msg?: string }) => {
          const field = e.loc?.slice(1).join(".") || "";
          return field ? `${field}: ${e.msg}` : e.msg;
        })
        .join("; ");
    } else if (typeof detail === "string") {
      message = detail;
    } else {
      message = error.message || "请求失败";
    }
    return Promise.reject(new Error(message));
  }
);

export { api };
