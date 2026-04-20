"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "../components/page-header";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "../components/recharts";
import { formatDate, formatNumber } from "../utils/format";
import { normalizeForecastSummary } from "../utils/normalize";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://gridflow-ai.onrender.com";
console.log("API URL:", API_BASE);

type ForecastRow = {
  ds: string;
  actual?: number;
  forecast?: number;
  lower?: number;
  upper?: number;
  band?: number;
};

const seriesOptions = [
  "total_demand",
  "Maharashtra",
  "Gujarat",
  "Tamil_Nadu",
  "Delhi",
  "UP",
];

export default function ForecastPage() {
  const [series, setSeries] = useState("total_demand");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<ForecastRow[]>([]);
  const [metrics, setMetrics] = useState({ mae: 0, rmse: 0, next: 0, change: 0 });
  const [tableRows, setTableRows] = useState<
    Array<{ ds: string; yhat: number; yhat_lower: number; yhat_upper: number }>
  >([]);
  const fetchForecastData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const base = API_BASE.endsWith("/") ? API_BASE.slice(0, -1) : API_BASE;
      const url = `${base}/api/v1/forecast/summary`;
      console.log("Calling:", url);
      const res = await fetch(url);
      if (!res.ok) {
        console.error("API failed", res.status);
        throw new Error("API error");
      }
      const payload = await res.json();
      const summary = normalizeForecastSummary(payload);
      console.log("DATA:", summary);
      const selected =
        summary.find((item) => item.series === series) ??
        summary.find((item) => item.series === "total_demand");

      const latestActual = selected?.latestActual ?? 0;
      const nextForecast = selected?.nextDayForecast ?? 0;
      const percentChange =
        latestActual === 0 ? 0 : ((nextForecast - latestActual) / latestActual) * 100;

      const baseDate = new Date();
      const composed: ForecastRow[] = Array.from({ length: 14 }).map((_, index) => {
        const day = new Date(baseDate);
        day.setDate(baseDate.getDate() + index);
        const drift = 1 + (percentChange / 100) * (index / 14);
        const forecast = nextForecast * drift;
        const lower = forecast * 0.95;
        const upper = forecast * 1.05;
        return {
          ds: day.toISOString().slice(0, 10),
          actual: index === 0 ? latestActual : undefined,
          forecast,
          lower,
          upper,
          band: upper - lower,
        };
      });

      setRows(composed);
      setMetrics({
        mae: selected?.mae ?? 0,
        rmse: selected?.rmse ?? 0,
        next: nextForecast,
        change: percentChange,
      });
      setTableRows(
        composed.map((item) => ({
          ds: item.ds,
          yhat: item.forecast ?? 0,
          yhat_lower: item.lower ?? 0,
          yhat_upper: item.upper ?? 0,
        })),
      );
    } catch (e) {
      console.error(e);
      setError("CONNECTION ERROR — is the backend running?");
      setRows([]);
      setTableRows([]);
    } finally {
      setLoading(false);
    }
  }, [series]);

  useEffect(() => {
    void fetchForecastData();
  }, [fetchForecastData]);

  const trendLabel = useMemo(
    () => (metrics.change >= 0 ? `+${formatNumber(metrics.change)}` : formatNumber(metrics.change)),
    [metrics.change],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Forecast"
        subtitle="Full explorer for historical load, forecast horizon, and confidence spread"
      />

      <section className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
        <label className="text-sm text-[#cccccc]" htmlFor="series-select">
          Forecast series
        </label>
        <select
          id="series-select"
          className="mt-2 w-full rounded border border-[#1a2a1a] bg-[#07080d] p-2 text-white"
          value={series}
          onChange={(event) => setSeries(event.target.value)}
        >
          {seriesOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </section>

      {loading ? <p className="text-sm text-[#00ff88]">LOADING...</p> : null}
      {error ? <p className="text-sm text-[#ff4455]">{error}</p> : null}

      <section className="min-w-0 rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={320}>
            <ComposedChart data={rows}>
              <CartesianGrid stroke="#1a2a1a" />
              <XAxis dataKey="ds" tick={{ fill: "#cccccc", fontSize: 11 }} />
              <YAxis
                tick={{ fill: "#cccccc", fontSize: 11 }}
                tickFormatter={(value: number) => `${formatNumber(value)} MU`}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "#0d1117", border: "1px solid #1a2a1a" }}
              />
              <Area
                type="monotone"
                dataKey="actual"
                fill="#888888"
                stroke="#888888"
                fillOpacity={0.2}
              />
              <Area type="monotone" dataKey="lower" stackId="conf" fillOpacity={0} strokeOpacity={0} />
              <Area
                type="monotone"
                dataKey="band"
                stackId="conf"
                fill="#00ff88"
                fillOpacity={0.14}
                strokeOpacity={0}
              />
              <Line
                type="monotone"
                dataKey="forecast"
                stroke="#00ff88"
                strokeWidth={2}
                strokeDasharray="6 4"
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">MAE</p>
          <p className="mt-2 text-xl font-bold">{formatNumber(metrics.mae)} MU</p>
        </article>
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">RMSE</p>
          <p className="mt-2 text-xl font-bold">{formatNumber(metrics.rmse)} MU</p>
        </article>
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">Tomorrow&apos;s Forecast</p>
          <p className="mt-2 text-xl font-bold">{formatNumber(metrics.next)} MU</p>
        </article>
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">% vs latest actual</p>
          <p className="mt-2 text-xl font-bold">{trendLabel}%</p>
        </article>
      </section>

      <section className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
        <p className="mb-3 text-sm text-[#cccccc]">Next 14 days forecast</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1a2a1a] text-left text-[#cccccc]">
              <th className="pb-2">Date</th>
              <th className="pb-2">Forecast</th>
              <th className="pb-2">Lower Bound</th>
              <th className="pb-2">Upper Bound</th>
              <th className="pb-2">Day</th>
            </tr>
          </thead>
          <tbody>
            {tableRows.map((item) => {
              const day = new Date(item.ds).toLocaleDateString(undefined, { weekday: "long" });
              return (
                <tr key={item.ds} className="border-b border-[#1a2a1a]">
                  <td className="py-2">{formatDate(item.ds)}</td>
                  <td className="py-2">{formatNumber(item.yhat)} MU</td>
                  <td className="py-2">{formatNumber(item.yhat_lower)} MU</td>
                  <td className="py-2">{formatNumber(item.yhat_upper)} MU</td>
                  <td className="py-2">{day}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}
