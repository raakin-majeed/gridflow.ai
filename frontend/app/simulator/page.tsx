"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "../components/page-header";
import { apiFetch } from "../utils/api";
import { formatNumber } from "../utils/format";
import { normalizeResponse, type NormalizedDecision } from "../utils/normalize";

const defaultResult: NormalizedDecision = {
  decision: "STORE",
  demand: 0,
  price: 0,
  revenue: 0,
  eva: 0,
  impact: 0,
  market_state: "Balanced",
  confidence: 50,
  alert: null,
  risk: "STABLE",
  explanation: "Awaiting model output.",
};

const decisionClass = (decision: string): string => {
  if (decision === "BUY") return "text-[#00ff88]";
  if (decision === "SELL") return "text-[#ff4455]";
  return "text-[#ffaa00]";
};

const STATES = ["Maharashtra", "Gujarat", "Tamil_Nadu", "Delhi", "UP"];

export default function SimulatorPage() {
  const [states] = useState<string[]>(STATES);
  const [region, setRegion] = useState("");
  const [temp, setTemp] = useState(30);
  const [solar, setSolar] = useState(2000);
  const [storage, setStorage] = useState(50);
  const [hour, setHour] = useState(14);
  const [festival, setFestival] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<NormalizedDecision>(defaultResult);

  const runAnalysis = useCallback(async () => {
    if (!region) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await apiFetch<unknown>("/api/v1/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          region,
          temp,
          solar_capacity: solar,
          storage_soc: storage,
          is_festival: festival,
          sim_hour: hour,
        }),
      });
      setResult(normalizeResponse(payload));
      setHasRun(true);
    } catch {
      setError("CONNECTION ERROR — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [festival, hour, region, solar, storage, temp]);

  useEffect(() => {
    setRegion(STATES[0]);
    setPageLoading(false);
  }, []);

  useEffect(() => {
    if (!hasRun) return;
    const timer = window.setTimeout(() => {
      void runAnalysis();
    }, 500);
    return () => window.clearTimeout(timer);
  }, [hasRun, temp, solar, storage, hour, runAnalysis]);

  const netLoad = useMemo(() => Math.max(result.demand - solar, 0), [result.demand, solar]);
  const healthScore = useMemo(() => {
    if (result.risk === "RED") return 45;
    if (result.risk === "AMBER") return 70;
    return 88;
  }, [result.risk]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Simulator"
        subtitle="Adjust grid assumptions and evaluate real-time decision response"
      />
      {pageLoading ? <p className="text-sm text-[#00ff88]">LOADING...</p> : null}
      {error ? <p className="text-sm text-[#ff4455]">{error}</p> : null}

      <section className="grid gap-4 xl:grid-cols-2">
        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          <h2 className="text-lg font-bold text-[#00ff88]">WHAT-IF SIMULATOR</h2>
          <p className="mb-4 text-sm text-[#cccccc]">
            Adjust parameters and see real-time grid response
          </p>

          <div className="space-y-4">
            <label className="block text-sm text-[#cccccc]">
              Region
              <select
                className="mt-1 w-full rounded border border-[#1a2a1a] bg-[#07080d] p-2 text-white"
                value={region}
                onChange={(event) => setRegion(event.target.value)}
              >
                {states.map((state) => (
                  <option key={state} value={state}>
                    {state}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm text-[#cccccc]">
              Temperature {temp} C
              <input
                type="range"
                min={20}
                max={50}
                value={temp}
                onChange={(event) => setTemp(Number(event.target.value))}
                className="mt-1 w-full"
              />
            </label>

            <label className="block text-sm text-[#cccccc]">
              Solar Capacity {solar} MW
              <input
                type="range"
                min={0}
                max={5000}
                value={solar}
                onChange={(event) => setSolar(Number(event.target.value))}
                className="mt-1 w-full"
              />
            </label>

            <label className="block text-sm text-[#cccccc]">
              Storage SOC {storage}%
              <input
                type="range"
                min={0}
                max={100}
                value={storage}
                onChange={(event) => setStorage(Number(event.target.value))}
                className="mt-1 w-full"
              />
            </label>

            <label className="block text-sm text-[#cccccc]">
              Hour {hour}
              <input
                type="range"
                min={0}
                max={23}
                value={hour}
                onChange={(event) => setHour(Number(event.target.value))}
                className="mt-1 w-full"
              />
            </label>

            <label className="flex items-center justify-between text-sm text-[#cccccc]">
              Festival
              <input
                type="checkbox"
                checked={festival}
                onChange={(event) => setFestival(event.target.checked)}
              />
            </label>

            <button
              className="w-full rounded border border-[#1a2a1a] bg-[#00ff88] py-2 font-bold text-black"
              onClick={() => void runAnalysis()}
              disabled={loading || !region}
            >
              {loading ? "RUNNING..." : "RUN ANALYSIS"}
            </button>
          </div>
        </article>

        <article className="rounded border border-[#1a2a1a] bg-[#0d1117] p-4">
          {!hasRun ? (
            <p className="text-sm text-[#cccccc]">
              AWAITING INPUT — adjust parameters and run analysis
            </p>
          ) : (
            <div className="space-y-5">
              <section className="rounded border border-[#1a2a1a] bg-[#07080d] p-4">
                <p className={`text-5xl font-bold ${decisionClass(result.decision)}`}>
                  {result.decision}
                </p>
                <p className="mt-2 text-sm text-[#cccccc]">Risk level: {result.risk}</p>
                <p className="mt-3 rounded border border-[#1a2a1a] bg-[#0d1117] p-3 text-sm text-white">
                  {result.explanation}
                </p>
              </section>

              <section>
                <p className="mb-2 text-sm text-[#cccccc]">Grid Metrics</p>
                <div className="grid gap-2 md:grid-cols-2">
                  <div className="rounded border border-[#1a2a1a] bg-[#07080d] p-3">
                    Demand {formatNumber(result.demand)} MW
                  </div>
                  <div className="rounded border border-[#1a2a1a] bg-[#07080d] p-3">
                    Solar {formatNumber(solar)} MW
                  </div>
                  <div className="rounded border border-[#1a2a1a] bg-[#07080d] p-3">
                    Net Load {formatNumber(netLoad)} MW
                  </div>
                  <div className="rounded border border-[#1a2a1a] bg-[#07080d] p-3">
                    Health Score {formatNumber(healthScore)}%
                    <div className="mt-2 h-2 rounded bg-[#07080d]">
                      <div
                        className="h-2 rounded bg-[#00ff88]"
                        style={{ width: `${Math.min(100, healthScore)}%` }}
                      />
                    </div>
                  </div>
                </div>
              </section>

              <section>
                <p className="mb-2 text-sm text-[#cccccc]">Economics</p>
                <div className="grid gap-2 md:grid-cols-3">
                  <div className="rounded border border-[#1a2a1a] bg-[#07080d] p-3">
                    Spot Price ₹{formatNumber(result.price)}/MWh
                  </div>
                  <div className="rounded border border-[#1a2a1a] bg-[#07080d] p-3">
                    Revenue ₹{formatNumber(result.revenue)}
                  </div>
                  <div className="rounded border border-[#1a2a1a] bg-[#07080d] p-3">
                    EVA ₹{formatNumber(result.eva)}
                  </div>
                </div>
              </section>
            </div>
          )}
        </article>
      </section>
    </div>
  );
}
