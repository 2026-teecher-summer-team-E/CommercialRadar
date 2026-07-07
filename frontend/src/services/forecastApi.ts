import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

export const forecastApi = {
  getSurvivalForecast: () => api.get("/api/forecast/survival"),
  getPopulationForecast: () => api.get("/api/forecast/population"),
  getSalesForecast: () => api.get("/api/forecast/sales"),
};
