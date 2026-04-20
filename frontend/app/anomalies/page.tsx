"use client";

import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "../components/page-header";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "../components/recharts";
import { apiFetch } from "../utils/api";
import { formatDateTime, formatNumber } from "../utils/format";
import { normalizeAnomalies, type NormalizedAnomalyItem } from "../utils/normalize";

const severityClass = (severity: string): string => {
  if (severity === "HIGH") return "text-[#ff4455]";
  if (severity === "MEDIUM") return "text-[#ffaa00]";
  return "text-[#00ff88]";
};

const dedupeWithinFiveSeconds = (rows: NormalizedAnomalyItem[]): NormalizedAnomalyItem[] => {
  const seen = new Map<string, number>();
  const sorted = [...rows].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );

  return sorted.filter((row) => {
    const ts = new Date(row.timestamp).getTime();
    const key = `${row.region}|${row.signal}|${row.severity}|${row.price}|${row.health}`;
    const prior = seen.get(key);
    if (typeof prior === "number" && Math.abs(prior - ts) <= 5000) return false;
    seen.set(key, ts);
    return true;
  });
};

export default function AnomaliesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [anomalies, setAnomalies] = useState<NormalizedAnomalyItem[]>([]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const payload = await apiFetch<unknown>("/api/v1/anomalies?limit=100");
        const normalized = dedupeWithinFiveSeconds(normalizeAnomalies(payload)).slice(0, 20);
        setAnomalies(normalized);
      } catch {
        setError("CONNECTION ERROR — is the backend running?");
        setAnomalies([]);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const criticalCount = useMemo(
    () => anomalies.filter((item) => item.severity === "HIGH").length,
    [anomalies],
  );

  const mostAffectedState = useMemo(() => {
    const counts = anomalies.reduce<Record<string, number>>((acc, item) => {
      acc[item.region] = (acc[item.region] ?? 0) + 1;
      return acc;
    }, {});
    const best = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
    return best?.[0] ?? "N/A";
  }, [anomalies]);

  const stateCounts = useMemo(() => {
    const counts = anomalies.reduce<Record<string, number>>((acc, item) => {
      acc[item.region] = (acc[item.region] ?? 0) + 1;
      return acc;
    }, {});
    return Object.entries(counts).map(([state, count]) => ({ state, count }));
  }, [anomalies]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Anomalies"
        subtitle="Detected irregular patterns and alert concentration by state"
      />
      {loading ? <p className="text-sm text-[#00ff88]">LOADING...</p> : null}
      {error ? <p className="text-sm text-[#ff4455]">{error}</p> : null}

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">Total Anomalies</p>
          <p className="mt-2 text-2xl font-bold">{anomalies.length} events</p>
        </article>
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">Critical Count</p>
          <p className="mt-2 text-2xl font-bold text-[#ff4455]">{criticalCount} events</p>
        </article>
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <p className="text-xs text-[#cccccc]">Most Affected State</p>
          <p className="mt-2 text-2xl font-bold">{mostAffectedState}</p>
        </article>
      </section>

      <section className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1a2a1a] text-left text-[#cccccc]">
              <th className="pb-2">Timestamp</th>
              <th className="pb-2">State</th>
              <th className="pb-2">Health Score</th>
              <th className="pb-2">Price</th>
              <th className="pb-2">Signal</th>
              <th className="pb-2">Severity</th>
            </tr>
          </thead>
          <tbody>
            {anomalies.map((item, index) => (
              <tr
                key={`${item.timestamp}-${item.region}-${index}`}
                className={index % 2 === 0 ? "bg-[#0d1117]" : "bg-[#0a0f0a]"}
              >
                <td className="py-2">{formatDateTime(item.timestamp)}</td>
                <td className="py-2">{item.region}</td>
                <td className="py-2">{formatNumber(item.health)}%</td>
                <td className="py-2">₹{formatNumber(item.price)}</td>
                <td className="py-2">{item.signal}</td>
                <td className={`py-2 ${severityClass(item.severity)}`}>{item.severity}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="min-w-0 rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
        <p className="mb-3 text-sm text-[#cccccc]">Anomaly count by state</p>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={200}>
            <BarChart data={stateCounts}>
              <CartesianGrid stroke="#1a2a1a" />
              <XAxis dataKey="state" tick={{ fill: "#cccccc", fontSize: 11 }} />
              <YAxis tick={{ fill: "#cccccc", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#0d1117", border: "1px solid #1a2a1a" }}
              />
              <Bar dataKey="count" fill="#00ff88" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
