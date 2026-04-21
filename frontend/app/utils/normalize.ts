type AnyRecord = Record<string, unknown>;

const toRecord = (value: unknown): AnyRecord =>
  value !== null && typeof value === "object" ? (value as AnyRecord) : {};

const toNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
};

const toString = (value: unknown, fallback = "UNKNOWN"): string =>
  typeof value === "string" && value.trim() !== "" ? value : fallback;

export type NormalizedDecision = {
  decision: string;
  demand: number;
  price: number;
  revenue: number;
  eva: number;
  impact: number;
  market_state: string;
  confidence: number;
  alert: string | null;
  risk: string;
  explanation: string;
  net_load_mw: number;
  health_score: number;
};

export type ForecastSummaryItem = {
  series: string;
  mae: number;
  rmse: number;
  latestActual: number;
  nextDayForecast: number;
};

export type RiskItem = {
  state: string;
  score: number;
  level: "RED" | "AMBER" | "GREEN";
};

export type RegionSummaryItem = {
  region: "North" | "West" | "South" | string;
  states: string[];
  demandTotal: number;
  demandChangePct: number;
  riskScore: number;
  riskLevel: "RED" | "AMBER" | "GREEN";
};

export type NormalizedHistoryItem = {
  timestamp: string;
  region: string;
  decision: string;
  price: number;
  risk: string;
};

export type NormalizedAnomalyItem = {
  timestamp: string;
  region: string;
  health: number;
  price: number;
  signal: string;
  severity: string;
};

export type ForecastPoint = {
  ds: string;
  yhat: number;
  yhat_lower: number;
  yhat_upper: number;
};

export type ActualPoint = {
  ds: string;
  y: number;
};

export type ForecastSeriesResponse = {
  series: string;
  metrics: { mae: number; rmse: number };
  actuals: ActualPoint[];
  forecast: ForecastPoint[];
};

export function normalizeResponse(data: unknown): NormalizedDecision {
  const root = toRecord(data);
  const decisionNode = toRecord(root.decision);

  return {
    decision: toString(decisionNode.signal ?? root.decision, "HOLD"),
    demand: toNumber(root.demand ?? root.forecast, 0),
    price: toNumber(root.price, 0),
    revenue: toNumber(root.revenue, 0),
    eva: toNumber(root.eva, 0),
    impact: toNumber(root.impact, 0),
    market_state: toString(root.market_state, "Balanced"),
    confidence: toNumber(root.confidence, 50),
    alert: typeof root.alert === "string" ? root.alert : null,
    risk: toString(decisionNode.risk ?? root.risk, "STABLE"),
    explanation: toString(
      decisionNode.rationale ?? root.explanation,
      "No explanation available",
    ),
    net_load_mw: toNumber(root.net_load_mw, 0),
    health_score: toNumber(root.health_score, 0),
  };
}

export function normalizeForecastSummary(data: unknown): ForecastSummaryItem[] {
  if (!Array.isArray(data)) return [];
  return data.map((item) => {
    const row = toRecord(item);
    return {
      series: toString(row.series),
      mae: toNumber(row.mae, 0),
      rmse: toNumber(row.rmse, 0),
      latestActual: toNumber(row.latest_actual, 0),
      nextDayForecast: toNumber(row.next_day_forecast, 0),
    };
  });
}

export function normalizeRisk(data: unknown): RiskItem[] {
  if (!Array.isArray(data)) return [];
  return data.map((item) => {
    const row = toRecord(item);
    const level = toString(row.risk_level, "AMBER");
    return {
      state: toString(row.state),
      score: toNumber(row.risk_score, 0),
      level: level === "RED" || level === "GREEN" ? level : "AMBER",
    };
  });
}

export function normalizeRegionSummary(data: unknown): RegionSummaryItem[] {
  if (!Array.isArray(data)) return [];
  return data.map((item) => {
    const row = toRecord(item);
    const level = toString(row.risk_level, "AMBER");
    const statesRaw = Array.isArray(row.states) ? row.states : [];
    const states = statesRaw.filter((state): state is string => typeof state === "string");

    return {
      region: toString(row.region),
      states,
      demandTotal: toNumber(row.demand_total, 0),
      demandChangePct: toNumber(row.demand_change_pct, 0),
      riskScore: toNumber(row.risk_score, 0),
      riskLevel: level === "RED" || level === "GREEN" ? level : "AMBER",
    };
  });
}

export function normalizeHistory(data: unknown): NormalizedHistoryItem[] {
  if (!Array.isArray(data)) return [];
  return data.map((item) => {
    const row = toRecord(item);
    const health = toNumber(row.health, 100);
    const risk = health < 60 ? "RED" : health < 80 ? "AMBER" : "GREEN";
    return {
      timestamp: toString(row.timestamp, ""),
      region: toString(row.region),
      decision: toString(row.signal ?? row.decision, "HOLD"),
      price: toNumber(row.price_val ?? row.price, 0),
      risk,
    };
  });
}

export function normalizeAnomalies(data: unknown): NormalizedAnomalyItem[] {
  if (!Array.isArray(data)) return [];
  return data.map((item) => {
    const row = toRecord(item);
    return {
      timestamp: toString(row.timestamp, ""),
      region: toString(row.region),
      health: toNumber(row.health_score ?? row.health, 0),
      price: toNumber(row.price, 0),
      signal: toString(row.signal, "UNKNOWN"),
      severity: toString(row.severity, "LOW"),
    };
  });
}

export function normalizeForecastSeries(data: unknown): ForecastSeriesResponse {
  const root = toRecord(data);
  const metricsNode = toRecord(root.metrics);
  const actualsInput = Array.isArray(root.actuals) ? root.actuals : [];
  const forecastInput = Array.isArray(root.forecast) ? root.forecast : [];

  return {
    series: toString(root.series),
    metrics: {
      mae: toNumber(metricsNode.mae, 0),
      rmse: toNumber(metricsNode.rmse, 0),
    },
    actuals: actualsInput.map((point) => {
      const row = toRecord(point);
      return {
        ds: toString(row.ds, ""),
        y: toNumber(row.y, 0),
      };
    }),
    forecast: forecastInput.map((point) => {
      const row = toRecord(point);
      return {
        ds: toString(row.ds, ""),
        yhat: toNumber(row.yhat, 0),
        yhat_lower: toNumber(row.yhat_lower, 0),
        yhat_upper: toNumber(row.yhat_upper, 0),
      };
    }),
  };
}
