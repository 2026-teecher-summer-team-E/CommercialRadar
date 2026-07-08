import { useEffect, useState } from "react";

import { forecastApi } from "../services/forecastApi";
import type { TimeseriesResponse } from "../types";

export function useTimeseries(
  districtId: number,
  category: string,
  metric: "sales" | "survival",
) {
  const [data, setData] = useState<TimeseriesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    forecastApi
      .getTimeseries(districtId, category, metric)
      .then((res) => {
        if (!cancelled) setData(res.data as TimeseriesResponse);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [districtId, category, metric]);

  return { data, loading, error };
}
