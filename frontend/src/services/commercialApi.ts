import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

export const commercialApi = {
  listDistricts: () => api.get("/api/commercial-districts"),
  getDistrict: (code: string) => api.get(`/api/commercial-districts/${code}`),
};
