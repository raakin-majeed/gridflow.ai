import math
import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import requests
import uvicorn
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

load_dotenv()
app = FastAPI(title="Strategic Arbitrage Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://gridflow-ai.vercel.app",
        "https://*.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def resolve_database_url() -> str:
    raw_url = os.getenv("DATABASE_URL", "").strip()
    if not raw_url:
        raw_url = f"sqlite:///{(PROJECT_ROOT / 'data' / 'gridflow.db').as_posix()}"

    if raw_url.startswith("sqlite:///"):
        db_path = raw_url.replace("sqlite:///", "", 1)
        path_obj = Path(db_path)
        if not path_obj.is_absolute():
            path_obj = (PROJECT_ROOT / path_obj).resolve()
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path_obj.as_posix()}"

    return raw_url


# Vercel/Postgres-ready database URL. Falls back to local SQLite for dev.
DATABASE_URL = resolve_database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)


class Base(DeclarativeBase):
    pass


class GridLog(Base):
    __tablename__ = "grid_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    demand: Mapped[float] = mapped_column(Float, nullable=False)
    solar: Mapped[float] = mapped_column(Float, nullable=False)
    health: Mapped[float] = mapped_column(Float, nullable=False)
    price_val: Mapped[float] = mapped_column(Float, nullable=False)
    is_fest: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    signal: Mapped[str] = mapped_column(String(16), nullable=False)
    eva: Mapped[float] = mapped_column(Float, nullable=False)
    carbon_credits_saved: Mapped[float] = mapped_column(Float, nullable=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {
        "status": "GridFlow AI Backend Running",
        "docs": "/docs",
        "message": "Use /docs to explore APIs"
    }


@app.options("/api/v1/analyze")
async def options_analyze():
    return {}


init_db()


class GridBrain:
    def __init__(self) -> None:
        self.base_loads = {
            "Northern": 850,
            "Western": 950,
            "Southern": 720,
            "Eastern": 510,
            "North-Eastern": 180,
        }

    def _price_model(self, hour: int, health: float, is_fest: bool) -> float:
        if 9 <= hour <= 16:
            base_price = 4.10
        elif (6 <= hour <= 9) or (18 <= hour <= 22):
            base_price = 11.85
        else:
            base_price = 6.50

        health_risk_premium = (100 - health) * 0.03
        festival_premium = 0.8 if is_fest else 0.0
        return round(base_price + health_risk_premium + festival_premium, 2)

    def _recommend_signal(
        self,
        price: float,
        health: float,
        net_load: float,
        demand: float,
        storage_soc: float,
    ) -> tuple[str, str]:
        load_ratio = (net_load / demand) if demand > 0 else 0.0

        # Arbitrage logic blends market opportunity and operational safety.
        if (price <= 5.0 and health >= 75) or (load_ratio < 0.65 and storage_soc < 90):
            return "BUY", "Import/charge now; low-price or low-stress window."
        if (price >= 9.5 and health >= 70 and storage_soc >= 20) or (health < 60):
            return "SELL", "Discharge/export now; monetise high tariffs or protect grid."
        return "STORE", "Hold position; preserve flexibility for next interval."

    def compute(
        self,
        region: str,
        temp: float,
        is_fest: bool,
        hour: int,
        solar_cap: float,
        storage_soc: float,
        operating_cost_per_mwh: float,
        capital_employed: float,
        wacc: float,
        carbon_credit_price: float,
    ) -> dict:
        base = self.base_loads.get(region, 50000)

        temp_mult = 1.0 + (max(0.0, temp - 30) * 0.025)
        fest_mult = 1.20 if is_fest else 1.0
        hour_mult = 1.18 if (18 <= hour <= 22) else 1.0
        demand = base * temp_mult * fest_mult * hour_mult

        if 6 <= hour <= 18:
            efficiency = math.sin((hour - 6) * math.pi / 12)
            solar = solar_cap * efficiency * random.uniform(0.90, 0.98)
        else:
            solar = 0.0

        net_load = max(0.0, demand - solar)
        health = 100 - (max(0.0, temp - 38) * 3) - min(40, (net_load / (base * 0.05)))
        health = max(0.0, min(100.0, round(health, 2)))

        price_val = self._price_model(hour, health, is_fest)
        signal, rationale = self._recommend_signal(
            price=price_val,
            health=health,
            net_load=net_load,
            demand=demand,
            storage_soc=storage_soc,
        )

        energy_mwh = net_load / 1000.0
        revenue = energy_mwh * price_val
        operating_cost = energy_mwh * operating_cost_per_mwh
        nopat = revenue - operating_cost
        capital_charge = capital_employed * wacc
        eva = round(nopat - capital_charge, 2)

        carbon_avoided_tco2 = round((solar / 1000.0) * 0.82, 4)
        carbon_credit_savings = round(carbon_avoided_tco2 * carbon_credit_price, 2)

        risk = "CRITICAL" if health < 60 else "WARNING" if health < 85 else "STABLE"

        with Session(engine) as session:
            session.add(
                GridLog(
                    timestamp=datetime.now(timezone.utc),
                    region=region,
                    demand=round(demand, 2),
                    solar=round(solar, 2),
                    health=health,
                    price_val=price_val,
                    is_fest=is_fest,
                    hour=hour,
                    signal=signal,
                    eva=eva,
                    carbon_credits_saved=carbon_credit_savings,
                )
            )
            session.commit()

        return {
            "metrics": {
                "demand_mw": round(demand, 2),
                "solar_mw": round(solar, 2),
                "net_load_mw": round(net_load, 2),
                "health_score": health,
                "storage_soc_percent": storage_soc,
            },
            "economics": {
                "spot_price_inr_per_mwh": price_val,
                "revenue_inr": round(revenue, 2),
                "operating_cost_inr": round(operating_cost, 2),
                "nopat_inr": round(nopat, 2),
                "capital_charge_inr": round(capital_charge, 2),
                "eva_inr": eva,
                "carbon_avoided_tco2": carbon_avoided_tco2,
                "carbon_credit_savings_inr": carbon_credit_savings,
            },
            "decision": {
                "signal": signal,
                "risk": risk,
                "rationale": rationale,
            },
        }


brain = GridBrain()
DATA_DIR = PROJECT_ROOT / "data"
FORECAST_DIR = DATA_DIR / "forecasts"

SERIES_FILE_MAP = {
    "total_demand": "total_demand",
    "Maharashtra": "Maharashtra",
    "Gujarat": "Gujarat",
    "Tamil_Nadu": "Tamil Nadu",
    "Delhi": "Delhi",
    "UP": "UP",
}

SERIES_METRICS = {
    "total_demand": {"mae": 303.8812, "rmse": 372.0095},
    "Maharashtra": {"mae": 44.8967, "rmse": 51.6118},
    "Gujarat": {"mae": 29.9953, "rmse": 36.1797},
    "Tamil_Nadu": {"mae": 49.8362, "rmse": 57.1924},
    "Delhi": {"mae": 34.4784, "rmse": 39.6050},
    "UP": {"mae": 76.3234, "rmse": 86.7671},
}


def get_latest_and_forecast(series: str) -> tuple[float, float]:
    alias_map = {
        "Tamil Nadu": "Tamil_Nadu",
        "TamilNadu": "Tamil_Nadu",
        "Uttar Pradesh": "UP",
    }
    series = alias_map.get(series, series)

    if series not in SERIES_FILE_MAP:
        raise HTTPException(status_code=400, detail=f"Unsupported region/series: {series}")

    file_series_name = SERIES_FILE_MAP[series]
    actuals_path = FORECAST_DIR / f"{file_series_name}_actuals.csv"
    forecast_path = FORECAST_DIR / f"{file_series_name}_forecast.csv"

    if not actuals_path.exists() or not forecast_path.exists():
        raise HTTPException(status_code=404, detail=f"Forecast files missing for {series}")

    actuals_df = pd.read_csv(actuals_path)
    forecast_df = pd.read_csv(forecast_path)

    if actuals_df.empty or forecast_df.empty:
        raise HTTPException(status_code=404, detail=f"Forecast data empty for {series}")

    actuals_df["ds"] = pd.to_datetime(actuals_df["ds"], errors="coerce")
    forecast_df["ds"] = pd.to_datetime(forecast_df["ds"], errors="coerce")
    actuals_df = actuals_df.dropna(subset=["ds", "y"]).sort_values("ds")
    forecast_df = forecast_df.dropna(subset=["ds", "yhat"]).sort_values("ds")

    if actuals_df.empty or forecast_df.empty:
        raise HTTPException(status_code=404, detail=f"Invalid forecast rows for {series}")

    latest = float(actuals_df.iloc[-1]["y"])
    boundary = actuals_df.iloc[-1]["ds"]
    next_rows = forecast_df[forecast_df["ds"] > boundary]

    if next_rows.empty:
        raise HTTPException(status_code=404, detail=f"No next forecast value for {series}")

    forecast_next = float(next_rows.iloc[0]["yhat"])
    return latest, forecast_next


class SimInput(BaseModel):
    region: str
    temp: float
    is_festival: bool
    solar_capacity: float = Field(ge=0)
    sim_hour: int = Field(ge=0, le=23)
    storage_soc: float = Field(default=50, ge=0, le=100)
    operating_cost_per_mwh: float = Field(default=3.25, ge=0)
    capital_employed: float = Field(default=25000, ge=0)
    wacc: float = Field(default=0.10, ge=0, le=1)
    carbon_credit_price: float = Field(default=1500, ge=0)


@app.post("/api/v1/analyze")
def analyze(data: SimInput) -> dict:
    result = brain.compute(
        region=data.region,
        temp=data.temp,
        is_fest=data.is_festival,
        hour=data.sim_hour,
        solar_cap=data.solar_capacity,
        storage_soc=data.storage_soc,
        operating_cost_per_mwh=data.operating_cost_per_mwh,
        capital_employed=data.capital_employed,
        wacc=data.wacc,
        carbon_credit_price=data.carbon_credit_price,
    )

    decision_data = result.get("decision", {})
    metrics = result.get("metrics", {})
    economics = result.get("economics", {})

    risk_level = str(decision_data.get("risk", "STABLE"))
    current_price = float(economics.get("spot_price_inr_per_mwh"))
    demand_volume = float(metrics.get("demand_mw"))
    health_score = float(metrics.get("health_score"))

    latest, forecast_next = get_latest_and_forecast(data.region)
    if latest == 0:
        raise HTTPException(status_code=400, detail=f"Latest actual is zero for {data.region}")

    percent_change = ((forecast_next - latest) / latest) * 100
    forecast_volume = forecast_next

    is_peak_hour = 18 <= data.sim_hour <= 22
    price = current_price
    price += percent_change * 0.15
    price += (60 - health_score) * 0.04
    if is_peak_hour:
        price *= 1.2
    future_price = max(0.5, price)

    demand_rising = percent_change > 1.0
    demand_falling = percent_change < -1.0
    price_rising = future_price > current_price
    price_low = current_price < 6.5

    if demand_rising and price_rising:
        decision = "SELL"
    elif demand_falling and price_low:
        decision = "BUY"
    else:
        decision = "STORE"

    # Standardized impact model: potential savings only (non-negative).
    impact = round(
        (future_price - current_price) * (demand_volume / 1000.0) * (data.storage_soc / 100.0),
        2,
    )
    if impact < 0:
        impact = 0

    if percent_change > 5:
        market_state = "Peak Demand"
    elif percent_change < -3:
        market_state = "Oversupply"
    else:
        market_state = "Balanced"

    if percent_change > 5:
        alert = "High demand spike expected"
    elif percent_change < -5:
        alert = "Oversupply detected"
    else:
        alert = None

    confidence = max(50, min(95, 100 - abs(percent_change * 4)))

    trend = "rising" if percent_change > 0 else "falling"
    price_delta = future_price - current_price

    print("LATEST:", latest)
    print("FORECAST:", forecast_next)
    print("CHANGE:", percent_change)
    print("PRICE:", future_price)

    explanation_text = (
        f"Demand is changing by {percent_change:.2f}% ({trend}) from latest actual to next forecast. "
        f"Current price: {current_price:.2f}, future price: {future_price:.2f}. "
        f"Price delta: {price_delta:.2f}. "
        f"Demand volume used for impact: {forecast_volume:.2f}. "
        f"Decision: {decision} based on demand and pricing momentum."
    )

    return {
        "decision": {
            "signal": decision,
            "risk": risk_level,
            "rationale": explanation_text
        },
        "demand": round(demand_volume / 1000.0, 2),
        "demand_unit": "MU",
        "price": round(current_price, 2),
        "price_unit": "INR/MWh",
        "net_load_mw": round(float(metrics.get("net_load_mw", 0.0)), 2),
        "health_score": round(float(metrics.get("health_score", 0.0)), 2),
        "revenue": round(current_price * demand_volume * 0.1, 2),
        "eva": round(current_price * demand_volume * 0.02, 2),
        "impact": impact,
        "impact_unit": "INR",
        "market_state": market_state,
        "confidence": round(confidence, 2),
        "percent_change": round(percent_change, 2),
        "future_price": round(future_price, 2),
        "alert": alert
    }


@app.get("/api/v1/history")
def get_history(limit: int = 200) -> list[dict]:
    safe_limit = max(1, min(limit, 1000))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, timestamp, region, demand, solar, health, price_val, is_fest, hour,
                       signal, eva, carbon_credits_saved
                FROM grid_logs
                ORDER BY timestamp DESC
                LIMIT :limit
                """
            ),
            {"limit": safe_limit},
        ).mappings()
        return [dict(r) for r in rows]


@app.get("/api/v1/decision-history")
def get_decision_history(limit: int = 200) -> list[dict]:
    safe_limit = max(1, min(limit, 1000))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT timestamp, region, signal, price_val, eva
                FROM grid_logs
                ORDER BY timestamp DESC
                LIMIT :limit
                """
            ),
            {"limit": safe_limit},
        ).mappings()

        return [
            {
                "timestamp": row["timestamp"],
                "region": row["region"],
                "decision": row["signal"],
                "price": float(row["price_val"]) if row["price_val"] is not None else 0.0,
                "impact": float(row["eva"]) if row["eva"] is not None else 0.0,
            }
            for row in rows
        ]


@app.get("/api/v1/anomalies")
def get_anomalies(limit: int = 50) -> list[dict]:
    def normalize(series: pd.Series) -> pd.Series:
        min_val = float(series.min())
        max_val = float(series.max())
        if max_val == min_val:
            # Neutral midpoint when there is no spread in anomaly scores.
            return pd.Series([0.5 for _ in series], index=series.index, dtype=float)
        return (series - min_val) / (max_val - min_val)

    safe_limit = max(1, min(limit, 500))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT timestamp, region, demand, signal, health, price_val
                FROM grid_logs
                ORDER BY timestamp DESC
                LIMIT :limit
                """
            ),
            {"limit": safe_limit},
        ).mappings()

        anomalies_raw: list[dict] = []
        for row in rows:
            health = float(row["health"]) if row["health"] is not None else 100.0
            price = float(row["price_val"]) if row["price_val"] is not None else 0.0

            if health < 60 or price >= 10:
                demand = float(row["demand"]) if row["demand"] is not None else 0.0
                health_gap = max(0.0, 100.0 - health)
                price_pressure = max(0.0, price - 10.0) * 10.0
                anomaly_score = health_gap + price_pressure

                anomalies_raw.append(
                    {
                        "timestamp": row["timestamp"],
                        "region": row["region"],
                        "state": row["region"],
                        "demand": demand,
                        "price": price,
                        "signal": row["signal"],
                        "anomaly_score": anomaly_score,
                        "raw_health": health,
                    }
                )

        if not anomalies_raw:
            return []

        df = pd.DataFrame(anomalies_raw)
        df["normalized"] = normalize(df["anomaly_score"].astype(float))
        df["health_score"] = ((1 - df["normalized"]) * 100).clip(lower=0, upper=100).round(2)

        def score_to_severity(score: float) -> str:
            if score >= 0.75:
                return "HIGH"
            if score >= 0.4:
                return "MEDIUM"
            return "LOW"

        df["severity"] = df["normalized"].apply(score_to_severity)
        df["message"] = df.apply(
            lambda row: (
                f"Health score {row['health_score']:.2f}, price {row['price']:.2f}, "
                f"signal {row['signal']}"
            ),
            axis=1,
        )
        df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["hour_bucket"] = df["timestamp_dt"].dt.strftime("%Y-%m-%d %H:00:00")
        df["hour_bucket"] = df["hour_bucket"].fillna(df["timestamp"].astype(str).str.slice(0, 13))
        df = df.sort_values(by="timestamp_dt", ascending=False)
        df = df.drop_duplicates(subset=["state", "hour_bucket"], keep="first")
        df = df.head(10)

        return [
            {
                "timestamp": row["timestamp"],
                "region": row["region"],
                "state": row["state"],
                "demand": float(row["demand"]),
                "price": float(row["price"]),
                "signal": row["signal"],
                "anomaly_score": float(row["anomaly_score"]),
                "health_score": float(row["health_score"]),
                "severity": row["severity"],
                "message": row["message"],
            }
            for _, row in df.iterrows()
        ]


@app.get("/api/v1/forecast/summary")
def forecast_summary() -> list[dict]:
    summary: list[dict] = []

    for api_series_name, file_series_name in SERIES_FILE_MAP.items():
        actuals_path = FORECAST_DIR / f"{file_series_name}_actuals.csv"
        forecast_path = FORECAST_DIR / f"{file_series_name}_forecast.csv"

        if not actuals_path.exists() or not forecast_path.exists():
            continue

        actuals_df = pd.read_csv(actuals_path)
        forecast_df = pd.read_csv(forecast_path)

        if actuals_df.empty or forecast_df.empty:
            continue

        actuals_df["ds"] = pd.to_datetime(actuals_df["ds"], errors="coerce")
        forecast_df["ds"] = pd.to_datetime(forecast_df["ds"], errors="coerce")
        actuals_df = actuals_df.dropna(subset=["ds", "y"])
        forecast_df = forecast_df.dropna(subset=["ds", "yhat"])

        if actuals_df.empty or forecast_df.empty:
            continue

        latest_actual_row = actuals_df.iloc[-1]
        max_actual_date = latest_actual_row["ds"]
        next_day_rows = forecast_df[forecast_df["ds"] > max_actual_date].sort_values("ds")
        if next_day_rows.empty:
            continue

        next_day_forecast_row = next_day_rows.iloc[0]
        metrics = SERIES_METRICS[api_series_name]

        summary.append(
            {
                "series": api_series_name,
                "mae": metrics["mae"],
                "rmse": metrics["rmse"],
                "latest_actual": float(latest_actual_row["y"]),
                "next_day_forecast": float(next_day_forecast_row["yhat"]),
            }
        )

    return summary


def get_forecast_summary() -> list[dict]:
    base = forecast_summary()
    return [
        {
            "series": item.get("series"),
            "next": item.get("next_day_forecast", 0),
            "mae": item.get("mae", 0),
            "rmse": item.get("rmse", 0),
        }
        for item in base
    ]


@app.get("/api/v1/weather")
def get_weather():

    api_key = os.getenv("OPENWEATHER_API_KEY")

    cities = {
        "Maharashtra": (19.07, 72.87),
        "Gujarat": (23.02, 72.57),
        "Tamil_Nadu": (13.08, 80.27),
        "Delhi": (28.61, 77.20),
        "UP": (26.84, 80.94)
    }

    results = {}

    for state, (lat, lon) in cities.items():
        try:
            if not api_key:
                raise ValueError("Missing OPENWEATHER_API_KEY")
            url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly&appid={api_key}&units=metric"
            res = requests.get(url, timeout=8).json()
            tomorrow = res["daily"][1]
            results[state] = round(tomorrow["temp"]["max"], 1)
        except Exception:
            results[state] = 30

    return results


@app.get("/api/v1/forecast/live-summary")
def live_summary():

    weather = get_weather()
    base = forecast_summary()  # reuse existing function if available

    output = []

    for item in base:
        state = item["series"]
        base_val = item.get("next_day_forecast", item.get("next", 0))

        temp = weather.get(state, 30)

        adjustment = max(0, temp - 30) * 0.018
        adjusted = base_val * (1 + adjustment)

        output.append({
            "series": state,
            "base_forecast": round(base_val, 2),
            "weather_adjusted_forecast": round(adjusted, 2),
            "adjustment_percent": round(adjustment * 100, 2),
            "live_temp": temp,
            "mae": item.get("mae", 0),
            "rmse": item.get("rmse", 0),
        })

    return output


def risk_level_from_score(score: float) -> str:
    if score < 40:
        return "GREEN"
    if score < 70:
        return "AMBER"
    return "RED"


def risk_recommendation_from_score(score: float) -> str:
    if score >= 70:
        return "Immediate action required — consider load shedding or emergency import"
    if score > 55:
        return "Elevated demand expected — pre-position battery storage"
    if score >= 40:
        return "Moderate stress — monitor closely through peak hours"
    return "Grid stable — optimal window for battery charging or maintenance"


def risk_all_data() -> list[dict]:
    states = ["Maharashtra", "Gujarat", "Tamil_Nadu", "Delhi", "UP"]
    results = []
    now_utc = datetime.now(timezone.utc)
    hour = datetime.now().hour
    hour_risk = 1 if (7 <= hour < 10 or 18 <= hour < 23) else 0

    anomalies_path = DATA_DIR / "anomalies.csv"
    anomaly_counts: dict[str, int] = {state: 0 for state in states}

    if anomalies_path.exists():
        try:
            anomalies_df = pd.read_csv(anomalies_path)
            state_column = next(
                (col for col in ["state", "region", "series"] if col in anomalies_df.columns),
                None,
            )
            timestamp_column = next(
                (
                    col
                    for col in ["timestamp", "ds", "date", "datetime"]
                    if col in anomalies_df.columns
                ),
                None,
            )
            if state_column and timestamp_column:
                anomalies_df[timestamp_column] = pd.to_datetime(
                    anomalies_df[timestamp_column], errors="coerce", utc=True
                )
                cutoff = pd.Timestamp(now_utc - timedelta(days=7))
                recent = anomalies_df[anomalies_df[timestamp_column] >= cutoff]
                for state in states:
                    aliases = {state, state.replace("_", " ")}
                    anomaly_counts[state] = int(recent[state_column].isin(aliases).sum())
        except Exception:
            pass
    else:
        # Fallback when anomalies.csv is unavailable: derive anomalies from recent grid logs.
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT region, COUNT(*) AS cnt
                    FROM grid_logs
                    WHERE timestamp >= :cutoff
                      AND (health < 60 OR price_val >= 10)
                    GROUP BY region
                    """
                ),
                {"cutoff": now_utc - timedelta(days=7)},
            ).mappings()
            for row in rows:
                region = str(row["region"])
                if region in anomaly_counts:
                    anomaly_counts[region] = int(row["cnt"])

    for s in states:
        file_series_name = SERIES_FILE_MAP.get(s, s)
        actuals_path = FORECAST_DIR / f"{file_series_name}_actuals.csv"

        latest_demand = 0.0
        mean_30day = 0.0
        mean_7day = 0.0
        demand_normalized = 1.0
        deviation_7day = 0.0

        if actuals_path.exists():
            df = pd.read_csv(actuals_path)
            df = df.dropna(subset=["y"])
            if not df.empty:
                tail_30 = df.tail(30).copy()
                tail_7 = df.tail(7).copy()
                latest_demand = float(df.iloc[-1]["y"])
                mean_30day = float(tail_30["y"].mean()) if not tail_30.empty else latest_demand
                mean_7day = float(tail_7["y"].mean()) if not tail_7.empty else latest_demand
                if mean_30day > 0:
                    demand_normalized = latest_demand / mean_30day
                if mean_7day > 0:
                    deviation_7day = ((latest_demand - mean_7day) / mean_7day) * 100

        anomaly_count = anomaly_counts.get(s, 0)
        anomaly_score = min(100.0, anomaly_count * 15.0)
        score = (
            (demand_normalized * 35.0)
            + (anomaly_score * 0.30)
            + (hour_risk * 20.0)
            + (abs(deviation_7day) * 0.15)
        )
        score = min(100.0, max(0.0, round(score, 2)))
        level = risk_level_from_score(score)
        recommendation = risk_recommendation_from_score(score)

        results.append({
            "state": s,
            "risk_score": score,
            "risk_level": level,
            "top_factors": [
                f"demand_norm={demand_normalized:.2f}",
                f"anomaly_count_7d={anomaly_count}",
                f"hour_risk={hour_risk}",
            ],
            "recommendation": recommendation
        })

    national_score = sum(item["risk_score"] for item in results) / len(results) if results else 0.0
    results.append(
        {
            "state": "NATIONAL",
            "risk_score": round(national_score, 2),
            "risk_level": risk_level_from_score(national_score),
            "top_factors": ["aggregated"],
            "recommendation": risk_recommendation_from_score(national_score),
        }
    )

    return results


RISK_CACHE_TTL_SECONDS = 60
_risk_cache_value: list[dict] = []
_risk_cache_computed_at = 0.0


def get_cached_risk_all_data() -> list[dict]:
    global _risk_cache_value, _risk_cache_computed_at
    now = time.time()
    cache_age = now - _risk_cache_computed_at

    if _risk_cache_value and cache_age < RISK_CACHE_TTL_SECONDS:
        return [dict(item) for item in _risk_cache_value]

    _risk_cache_value = risk_all_data()
    _risk_cache_computed_at = now
    return [dict(item) for item in _risk_cache_value]


REGION_GROUPS = {
    "North": ["Delhi", "UP"],
    "West": ["Maharashtra", "Gujarat"],
    "South": ["Tamil_Nadu"],
}


def region_summary_data() -> list[dict]:
    forecast_rows = forecast_summary()
    risk_rows = get_cached_risk_all_data()

    forecast_by_series = {
        str(item.get("series")): item for item in forecast_rows if isinstance(item, dict)
    }
    risk_by_state = {
        str(item.get("state")): item for item in risk_rows if isinstance(item, dict)
    }

    output: list[dict] = []

    for region_name, states in REGION_GROUPS.items():
        demand_total = 0.0
        latest_total = 0.0
        risk_scores: list[float] = []

        for state in states:
            forecast_item = forecast_by_series.get(state, {})
            next_forecast = float(forecast_item.get("next_day_forecast", 0) or 0)
            latest_actual = float(forecast_item.get("latest_actual", 0) or 0)

            demand_total += next_forecast
            latest_total += latest_actual

            risk_item = risk_by_state.get(state, {})
            risk_scores.append(float(risk_item.get("risk_score", 0) or 0))

        demand_change_pct = (
            ((demand_total - latest_total) / latest_total) * 100
            if latest_total > 0
            else 0.0
        )
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0

        risk_level = risk_level_from_score(avg_risk)

        output.append(
            {
                "region": region_name,
                "states": states,
                "demand_total": round(demand_total, 2),
                "demand_change_pct": round(demand_change_pct, 2),
                "risk_score": round(avg_risk, 2),
                "risk_level": risk_level,
            }
        )

    return output


@app.get("/api/v1/risk-score/all")
def risk_all():
    return get_cached_risk_all_data()


@app.get("/api/v1/regions/summary")
def regions_summary():
    return region_summary_data()


@app.post("/api/v1/query")
def query_ai(body: dict):
    question = str(body.get("question", "")).strip()
    if not question:
        return {
            "answer": "Please provide a question for GRIDFLOW AI.",
            "error": True
        }

    # collect system data
    forecast = get_forecast_summary()
    anomalies = get_anomalies()[:5]
    risk = risk_all()

    context = f"""
Forecast Data:
{forecast}

Risk Data:
{risk}

Recent Anomalies:
{anomalies}
"""
    system_prompt = f"""You are GridFlow AI, an expert electricity grid analyst for India. 
You have access to real-time demand forecasts, anomaly detection results, and risk scores for Indian states.

STRICT RULES:
1. You ONLY answer questions about electricity, energy, power grids, demand forecasting, grid management, or the Indian energy sector.
2. If the user asks ANYTHING outside of these topics — mathematics, general knowledge, coding, personal questions, or anything unrelated to energy/electricity — respond with exactly: "I can only answer questions about electricity demand, grid operations, and energy management. Please ask me something related to the Indian power grid."
3. Never perform calculations, answer trivia, write code, or engage in general conversation.
4. Always reference specific numbers from the data provided in your answer.
5. Keep answers to 2-3 sentences maximum. Be direct and actionable.

You have access to the following live grid data:
{context}"""

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return {
            "answer": "Missing GROQ_API_KEY in environment variables",
            "error": True
        }

    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"{context}\n\nQuestion: {question}"
                    }
                ],
                "temperature": 0.3
            },
            timeout=20,
        )

        result = response.json()

        # safe extraction
        if "choices" not in result:
            error_message = (
                result.get("error", {}).get("message")
                if isinstance(result, dict)
                else None
            )
            return {
                "answer": error_message or "Groq API error",
                "raw_response": result
            }

        answer = result["choices"][0]["message"]["content"]

        return {
            "answer": answer,
            "data_used": ["forecast", "anomalies", "risk"]
        }

    except Exception as e:
        return {
            "answer": "Error calling Groq API",
            "error": str(e)
        }


@app.get("/api/v1/forecast/{series}")
def forecast_series(series: str) -> dict:
    if series not in SERIES_FILE_MAP:
        raise HTTPException(status_code=404, detail="Unsupported forecast series.")

    file_series_name = SERIES_FILE_MAP[series]
    actuals_path = FORECAST_DIR / f"{file_series_name}_actuals.csv"
    forecast_path = FORECAST_DIR / f"{file_series_name}_forecast.csv"

    if not actuals_path.exists() or not forecast_path.exists():
        raise HTTPException(status_code=404, detail="Forecast files not found.")

    actuals_df = pd.read_csv(actuals_path)
    forecast_df = pd.read_csv(forecast_path)

    actuals_df["ds"] = pd.to_datetime(actuals_df["ds"], errors="coerce")
    forecast_df["ds"] = pd.to_datetime(forecast_df["ds"], errors="coerce")
    actuals_df = actuals_df.dropna(subset=["ds", "y"]).sort_values("ds")
    forecast_df = forecast_df.dropna(subset=["ds", "yhat", "yhat_lower", "yhat_upper"]).sort_values(
        "ds"
    )

    if actuals_df.empty or forecast_df.empty:
        raise HTTPException(status_code=404, detail="Forecast data is empty.")

    max_actual_date = actuals_df["ds"].max()
    future_forecast = forecast_df[forecast_df["ds"] > max_actual_date].head(30).copy()
    recent_actuals = actuals_df.tail(60).copy()

    future_forecast["ds"] = future_forecast["ds"].dt.strftime("%Y-%m-%d")
    recent_actuals["ds"] = recent_actuals["ds"].dt.strftime("%Y-%m-%d")

    return {
        "series": series,
        "forecast": future_forecast.to_dict(orient="records"),
        "actuals": recent_actuals.to_dict(orient="records"),
        "metrics": SERIES_METRICS[series],
    }


@app.get("/api/v1/report/{series}")
def generate_report(series: str):

    # mock using forecast logic
    forecast = []

    for i in range(7):
        forecast.append({
            "day": f"Day {i+1}",
            "expected_demand": 400 + i * 10,
            "expected_price": 5 + i * 0.2,
            "decision": "BUY" if i % 2 == 0 else "SELL"
        })

    return {
        "series": series,
        "forecast": forecast,
        "summary": "7-day projected demand and pricing trends with recommended actions."
    }


@app.get("/api/v1/states")
def get_states():
    return ["Maharashtra", "Gujarat", "Tamil Nadu", "Delhi", "UP"]


@app.get("/ping")
async def ping():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
