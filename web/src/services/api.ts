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
    const message =
      error.response?.data?.detail || error.message || "请求失败";
    return Promise.reject(new Error(message));
  }
);

export { api };
