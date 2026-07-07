import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

export const populationApi = {
  getPopulation: () => api.get("/api/population"),
  getStreetPopulation: () => api.get("/api/street-population"),
};
