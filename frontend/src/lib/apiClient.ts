import axios from "axios";

/** 공용 axios 인스턴스. baseURL 은 VITE_API_URL(.env). 경로는 각 서비스에서 `/api/...` 로 붙인다. */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "",
});
