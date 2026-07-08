import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TimeseriesPoint } from "../../types";
import { formatCurrency, formatPercent } from "../../utils/formatters";

interface Props {
  history: TimeseriesPoint[];
  forecast: TimeseriesPoint[];
  unit: "won" | "ratio";
}

interface Row {
  quarter: string;
  actual: number | null;
  low: number | null;
  mid: number | null;
  high: number | null;
  band: [number, number] | null;
}

export default function ForecastChart({ history, forecast, unit }: Props) {
  const rows: Row[] = [
    ...history.map((p) => ({
      quarter: p.year_quarter,
      actual: p.value,
      low: null as number | null,
      mid: null as number | null,
      high: null as number | null,
      band: null as [number, number] | null,
    })),
    ...forecast.map((p) => {
      const low = (p.low ?? p.value) as number | null;
      const mid = (p.mid ?? p.value) as number | null;
      const high = (p.high ?? p.value) as number | null;
      return {
        quarter: p.year_quarter,
        actual: null as number | null,
        low,
        mid,
        high,
        band: low != null && high != null ? ([low, high] as [number, number]) : null,
      };
    }),
  ];

  // 경계 연결: 마지막 과거점이 세 시나리오·밴드의 시작점이 되도록 채운다.
  if (history.length > 0 && forecast.length > 0) {
    const b = rows[history.length - 1];
    const a = b.actual;
    b.low = a;
    b.mid = a;
    b.high = a;
    b.band = a != null ? [a, a] : null;
  }

  const formatValue = (v: number) =>
    unit === "won" ? formatCurrency(v) : formatPercent(v);
  const formatAxis = (v: number) =>
    unit === "won" ? `${Math.round(v / 1e8)}억` : `${Math.round(v * 100)}%`;

  return (
    <ResponsiveContainer width="100%" height={380}>
      <ComposedChart data={rows} margin={{ top: 16, right: 24, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="quarter" tick={{ fontSize: 12 }} />
        <YAxis tickFormatter={formatAxis} width={64} tick={{ fontSize: 12 }} />
        <Tooltip
          formatter={(value, name) => [
            value == null ? "-" : formatValue(Number(value)),
            name,
          ]}
        />
        <Legend />
        <Area
          dataKey="band"
          name="예측 범위"
          stroke="none"
          fill="#6366f1"
          fillOpacity={0.12}
          connectNulls
          legendType="none"
        />
        <Line
          type="monotone"
          dataKey="actual"
          name="실적"
          stroke="#111827"
          strokeWidth={2}
          dot={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="high"
          name="낙관(p90)"
          stroke="#16a34a"
          strokeWidth={1.5}
          strokeDasharray="5 5"
          dot={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="mid"
          name="기준(p50)"
          stroke="#2563eb"
          strokeWidth={2}
          strokeDasharray="5 5"
          dot={{ r: 2 }}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="low"
          name="비관(p10)"
          stroke="#dc2626"
          strokeWidth={1.5}
          strokeDasharray="5 5"
          dot={false}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
