import { useState } from "react";

import ForecastChart from "../components/charts/ForecastChart";
import { useTimeseries } from "../hooks/useTimeseries";

const DISTRICT_ID = 1315;
const CATEGORY = "커피-음료";

export default function GangnamCafeDemoPage() {
  const [metric, setMetric] = useState<"sales" | "survival">("sales");
  const { data, loading, error } = useTimeseries(DISTRICT_ID, CATEGORY, metric);

  const hasData = data && (data.history.length > 0 || data.forecast.length > 0);

  return (
    <div style={{ maxWidth: 900, margin: "40px auto", padding: 16 }}>
      <h1>강남역 상권 · 카페(커피-음료)</h1>
      <p style={{ color: "#555" }}>
        과거 실적(실선)과 3개의 미래(비관·기준·낙관, 점선 + 예측 범위 밴드)
      </p>

      <div style={{ display: "flex", gap: 8, margin: "16px 0" }}>
        <button onClick={() => setMetric("sales")} disabled={metric === "sales"}>
          매출
        </button>
        <button onClick={() => setMetric("survival")} disabled={metric === "survival"}>
          생존율
        </button>
      </div>

      {loading && <p>불러오는 중…</p>}
      {!!error && <p>데이터를 불러오지 못했습니다.</p>}
      {hasData && (
        <ForecastChart history={data.history} forecast={data.forecast} unit={data.unit} />
      )}
      {!loading && !error && !hasData && <p>표시할 데이터가 없습니다.</p>}
    </div>
  );
}
