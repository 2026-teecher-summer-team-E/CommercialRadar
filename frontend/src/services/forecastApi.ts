import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

export const forecastApi = {
  getTimeseries: (districtId: number, category: string, metric: "sales" | "survival") =>
    api.get(`/api/commercial-districts/${districtId}/timeseries`, {
      params: { category_name: category, metric },
    }),
};
