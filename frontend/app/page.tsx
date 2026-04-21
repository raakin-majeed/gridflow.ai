"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "./components/page-header";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "./components/recharts";
import { formatDateTime, formatNumber } from "./utils/format";
import {
  normalizeAnomalies,
  normalizeForecastSummary,
  type NormalizedAnomalyItem,
} from "./utils/normalize";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://gridflow-ai.onrender.com";
console.log("API URL:", API_BASE);

type DashboardChartPoint = {
  ds: string;
  actual?: number;
  forecast?: number;
};

type RiskItem = {
  state: string;
  score: number;
  level: "RED" | "AMBER" | "GREEN";
  decision: string;
  recommendation: string;
};

type RegionSummaryItem = {
  region: "North" | "West" | "South";
  states: string[];
  demandTotal: number;
  demandChangePct: number;
  riskScore: number;
  riskLevel: "RED" | "AMBER" | "GREEN";
};

const REGION_GROUPS: Record<RegionSummaryItem["region"], string[]> = {
  North: ["Delhi", "UP"],
  West: ["Maharashtra", "Gujarat"],
  South: ["Tamil_Nadu"],
};

const levelColor = (level: string): string => {
  if (level === "RED") return "bg-[#ff4455]";
  if (level === "AMBER") return "bg-[#ffaa00]";
  return "bg-[#00ff88]";
};

const levelTextClass = (level: string): string => {
  if (level === "RED") return "text-[#ff4455]";
  if (level === "AMBER") return "text-[#ffaa00]";
  return "text-[#00ff88]";
};

const decisionClass = (decision: string): string => {
  if (decision === "BUY") return "text-[#00ff88]";
  if (decision === "SELL") return "text-[#ff4455]";
  return "text-[#ffaa00]";
};

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<
    Array<{ series: string; mae: number; rmse: number; latestActual: number; nextDayForecast: number }>
  >([]);
  const [risk, setRisk] = useState<RiskItem[]>([]);
  const [anomalies, setAnomalies] = useState<NormalizedAnomalyItem[]>([]);
  const [regionSummary, setRegionSummary] = useState<RegionSummaryItem[]>([]);
  const [chartData, setChartData] = useState<DashboardChartPoint[]>([]);

  useEffect(() => {
    console.log("CLIENT RUNNING");
    const summaryUrl = `${API_BASE}/api/v1/forecast/summary`;
    console.log("Calling:", summaryUrl);
    fetch(summaryUrl)
      .then((res) => {
        if (!res.ok) {
          console.error("API failed", res.status);
          throw new Error("API error");
        }
        return res.json();
      })
      .then((data) => console.log("DATA:", data))
      .catch((err) => console.error(err));
  }, []);

  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const base = API_BASE.endsWith("/") ? API_BASE.slice(0, -1) : API_BASE;
      const summaryUrl = `${base}/api/v1/forecast/summary`;
      const anomaliesUrl = `${base}/api/v1/anomalies`;
      console.log("Calling:", summaryUrl);
      console.log("Calling:", anomaliesUrl);
      const results = await Promise.allSettled([
        fetch(summaryUrl),
        fetch(anomaliesUrl),
      ]);

      const anyFailed = results.some((result) => result.status === "rejected");
      if (anyFailed) {
        setError("CONNECTION ERROR — is the backend running?");
      }

      const [summaryRes, anomalyRes] = results;

      if (summaryRes.status === "fulfilled") {
        if (!summaryRes.value.ok) {
          console.error("API failed", summaryRes.value.status);
          throw new Error("API error");
        }
        const summaryJson = await summaryRes.value.json();
        const normalizedSummary = normalizeForecastSummary(summaryJson);
        console.log("DATA:", normalizedSummary);
        setSummary(normalizedSummary);
        setChartData(
          normalizedSummary
            .filter((item) => item.series !== "total_demand")
            .map((item) => ({
              ds: item.series,
              actual: item.latestActual,
              forecast: item.nextDayForecast,
            })),
        );

        const riskResponse = await fetch(`${API_BASE}/api/v1/risk-score/all`);
        if (!riskResponse.ok) {
          console.error("API failed", riskResponse.status);
          throw new Error("API error");
        }
        const riskData = (await riskResponse.json()) as Array<{
          state: string;
          risk_score: number;
          risk_level: string;
          recommendation: string;
        }>;
        const riskRows: RiskItem[] = riskData
          .filter((row: { state: string }) => row.state !== "NATIONAL")
          .map((row: { state: string; risk_score: number; risk_level: string; recommendation: string }) => {
            const level: RiskItem["level"] =
              row.risk_level === "RED" || row.risk_level === "GREEN"
                ? row.risk_level
                : "AMBER";
            const decision = level === "RED" ? "SELL" : level === "GREEN" ? "BUY" : "STORE";

            return {
              state: row.state,
              score: row.risk_score,
              level,
              decision,
              recommendation: row.recommendation,
            };
          });
        setRisk(riskRows);

        const bySeries = new Map(normalizedSummary.map((item) => [item.series, item]));
        const regionRows: RegionSummaryItem[] = (Object.keys(REGION_GROUPS) as RegionSummaryItem["region"][]).map(
          (regionName) => {
            const states = REGION_GROUPS[regionName];
            let demandTotal = 0;
            let latestTotal = 0;
            const riskScores: number[] = [];

            states.forEach((state) => {
              const summaryItem = bySeries.get(state);
              demandTotal += summaryItem?.nextDayForecast ?? 0;
              latestTotal += summaryItem?.latestActual ?? 0;
              const riskItem = riskRows.find((item) => item.state === state);
              riskScores.push(riskItem?.score ?? 55);
            });

            const demandChangePct =
              latestTotal === 0 ? 0 : ((demandTotal - latestTotal) / latestTotal) * 100;
            const riskScore =
              riskScores.length === 0
                ? 0
                : riskScores.reduce((sum, value) => sum + value, 0) / riskScores.length;
            const riskLevel: RegionSummaryItem["riskLevel"] =
              riskScore < 33 ? "GREEN" : riskScore < 66 ? "AMBER" : "RED";

            return {
              region: regionName,
              states,
              demandTotal,
              demandChangePct,
              riskScore,
              riskLevel,
            };
          },
        );
        setRegionSummary(regionRows);
      }
      if (anomalyRes.status === "fulfilled") {
        if (!anomalyRes.value.ok) {
          console.error("API failed", anomalyRes.value.status);
          throw new Error("API error");
        }
        const anomalyJson = await anomalyRes.value.json();
        console.log("ANOMALIES:", anomalyJson);
        setAnomalies(normalizeAnomalies(anomalyJson).slice(0, 5));
      }

      setLoading(false);
    } catch (e) {
      console.error(e);
      setError("CONNECTION ERROR — is the backend running?");
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchDashboardData();
  }, [fetchDashboardData]);

  const totalDemandTomorrow = useMemo(() => {
    const total = summary.find((item) => item.series === "total_demand");
    return total?.nextDayForecast ?? 0;
  }, [summary]);

  const highestRisk = useMemo(() => {
    return [...risk].sort((a, b) => b.score - a.score)[0] ?? null;
  }, [risk]);

  const bestAccuracy = useMemo(() => {
    return [...summary].sort((a, b) => a.mae - b.mae)[0] ?? null;
  }, [summary]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle="Morning briefing for India grid operations and market posture"
      />
      <button
        onClick={() => console.log("CLICK WORKING")}
        className="rounded border border-[#1a2a1a] bg-[#0d1117] px-3 py-2 text-sm text-white"
      >
        TEST BUTTON
      </button>

      {loading ? <p className="text-sm text-[#00ff88]">LOADING...</p> : null}
      {error ? <p className="text-sm text-[#ff4455]">{error}</p> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">National Demand Tomorrow</p>
          <p className="mt-2 text-2xl font-bold">{formatNumber(totalDemandTomorrow)} MU</p>
        </article>
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">Highest Risk State</p>
          <div className="mt-2 flex items-center gap-2">
            <p className="text-xl font-bold">{highestRisk?.state ?? "N/A"}</p>
            <span
              className={`rounded px-2 py-1 text-xs font-bold ${levelTextClass(highestRisk?.level ?? "GREEN")}`}
            >
              {highestRisk?.level ?? "GREEN"}
            </span>
          </div>
        </article>
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">Active Anomalies</p>
          <p className="mt-2 text-2xl font-bold">{anomalies.length} events</p>
        </article>
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">Best Forecast Accuracy</p>
          <p className="mt-2 text-xl font-bold">{bestAccuracy?.series ?? "N/A"}</p>
          <p className="text-xs text-[#cccccc]">MAE {formatNumber(bestAccuracy?.mae ?? 0)} MU</p>
        </article>
      </section>

      <section className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
        <p className="mb-3 text-sm text-[#cccccc]">Region View</p>
        <div className="grid gap-4 md:grid-cols-3">
          {regionSummary.map((item) => (
            <article key={item.region} className="rounded border border-[#1a2a1a] bg-[#07080d] p-3">
              <p className="text-sm font-bold text-white">{item.region}</p>
              <p className={`mt-2 text-xs ${levelTextClass(item.riskLevel)}`}>
                {item.region} Region Risk: {formatNumber(item.riskScore)} pts ({item.riskLevel})
              </p>
              <p className="mt-2 text-xs text-[#cccccc]">
                {item.region} Region Demand Trend: {formatNumber(item.demandTotal)} MU (
                {item.demandChangePct >= 0 ? "+" : ""}
                {formatNumber(item.demandChangePct)}%)
              </p>
              <p className="mt-1 text-xs text-[#cccccc]">States: {item.states.join(", ")}</p>
            </article>
          ))}
          {regionSummary.length === 0 ? (
            <p className="text-sm text-[#cccccc]">No regional aggregates available.</p>
          ) : null}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-5">
        <article className="min-w-0 rounded border border-[#1a2a1a] bg-[#0d1117] p-4 xl:col-span-3">
          <p className="mb-3 text-sm text-[#cccccc]">State demand outlook (MU)</p>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={260}>
              <AreaChart data={chartData}>
                <CartesianGrid stroke="#1a2a1a" />
                <XAxis dataKey="ds" tick={{ fill: "#cccccc", fontSize: 11 }} />
                <YAxis tick={{ fill: "#cccccc", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0d1117", border: "1px solid #1a2a1a" }}
                />
                <Area
                  type="monotone"
                  dataKey="actual"
                  stroke="#999999"
                  fill="#999999"
                  fillOpacity={0.2}
                />
                <Area
                  type="monotone"
                  dataKey="forecast"
                  stroke="#00ff88"
                  fillOpacity={0}
                  strokeDasharray="6 4"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </article>
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4 xl:col-span-2">
          <p className="mb-4 text-sm text-[#cccccc]">Risk scores by state</p>
          <div className="space-y-3">
            {risk.map((item) => (
              <div key={item.state}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span>{item.state}</span>
                  <span>{formatNumber(item.score)} pts</span>
                </div>
                <div className="h-2 w-full rounded bg-[#07080d]">
                  <div
                    className={`h-2 rounded ${levelColor(item.level)}`}
                    style={{ width: `${Math.min(100, Math.max(0, item.score))}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="mb-3 text-sm text-[#cccccc]">Latest anomalies</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1a2a1a] text-left text-[#cccccc]">
                <th className="pb-2">Time</th>
                <th className="pb-2">State</th>
                <th className="pb-2">Severity</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((row, index) => (
                <tr key={`${row.timestamp}-${row.region}-${index}`} className="border-b border-[#1a2a1a]">
                  <td className="py-2">{formatDateTime(row.timestamp)}</td>
                  <td className="py-2">{row.region}</td>
                  <td className={`py-2 ${levelTextClass(row.severity === "HIGH" ? "RED" : "AMBER")}`}>
                    {row.severity}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="mb-3 text-sm text-[#cccccc]">Recent state decisions</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1a2a1a] text-left text-[#cccccc]">
                <th className="pb-2">Time</th>
                <th className="pb-2">Region</th>
                <th className="pb-2">Decision</th>
              </tr>
            </thead>
            <tbody>
              {risk.map((row, index) => (
                <tr key={`${row.state}-${index}`} className="border-b border-[#1a2a1a]">
                  <td className="py-2">{formatDateTime(new Date().toISOString())}</td>
                  <td className="py-2">{row.state}</td>
                  <td className={`py-2 font-bold ${decisionClass(row.decision)}`}>{row.decision}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      </section>
    </div>
  );
}
