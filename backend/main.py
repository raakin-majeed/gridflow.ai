import math
import os
import random
from datetime import datetime, timezone
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
app = FastAPI()
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


app = FastAPI(title="Strategic Arbitrage Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


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
            "Northern": 85000,
            "Western": 105000,
            "Southern": 72000,
            "Eastern": 51000,
            "North-Eastern": 18000,
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
        health = 100 - (max(0.0, temp - 38) * 5) - (net_load / (base / 10))
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

    decision_data = result.get("decision", {}) if isinstance(result, dict) else {}
    metrics = result.get("metrics", {}) if isinstance(result, dict) else {}
    economics = result.get("economics", {}) if isinstance(result, dict) else {}

    decision = decision_data.get("signal", "UNKNOWN")
    risk_level = decision_data.get("risk", "UNKNOWN")
    next_forecast = metrics.get("demand_mw", 0)
    current_price = economics.get("spot_price_inr_per_mwh", 0)
    percent_change = result.get("percent_change", 0) if isinstance(result, dict) else 0

    next_forecast = float(next_forecast) if 'next_forecast' in locals() else 400.0
    current_price = float(current_price) if 'current_price' in locals() else 5.0
    percent_change = float(percent_change) if 'percent_change' in locals() else 0.0

    future_price = current_price * (1 + percent_change / 100)

    decision = decision if 'decision' in locals() else "HOLD"

    risk_level = risk_level if 'risk_level' in locals() else "STABLE"

    price_diff = future_price - current_price

    scale = 0.001  # convert MW scale

    if decision == "BUY":
        impact = price_diff * next_forecast * scale
    elif decision == "SELL":
        impact = (-price_diff) * next_forecast * scale
    else:
        impact = 0

    if abs(impact) < 1:
        impact = impact * 100  # amplify small signals

    impact = round(impact, 2)

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

    confidence = 100 - abs(percent_change * 5)
    confidence = max(50, min(95, confidence))

    trend = "rising" if percent_change > 0 else "falling"

    explanation_text = f"""
Demand is {trend} by {abs(percent_change):.2f}%.
Current price: {current_price:.2f}, expected: {future_price:.2f}.
Market condition: {market_state}.
Recommended action: {decision}.
"""

    return {
        "decision": {
            "signal": decision,
            "risk": risk_level,
            "rationale": explanation_text.strip()
        },
        "demand": round(next_forecast, 2),
        "price": round(current_price, 2),
        "revenue": round(current_price * next_forecast * 0.1, 2),
        "eva": round(current_price * next_forecast * 0.02, 2),
        "impact": impact,
        "market_state": market_state,
        "confidence": round(confidence, 2),
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

        anomalies: list[dict] = []
        for row in rows:
            health = float(row["health"]) if row["health"] is not None else 100.0
            price = float(row["price_val"]) if row["price_val"] is not None else 0.0

            if health < 60 or price >= 10:
                severity = "HIGH" if (health < 60 or price >= 12) else "MEDIUM"
                message = (
                    f"Health {health:.2f}, price {price:.2f}, signal {row['signal']}"
                )
                anomalies.append(
                    {
                        "timestamp": row["timestamp"],
                        "region": row["region"],
                        "demand": float(row["demand"]) if row["demand"] is not None else 0.0,
                        "price": price,
                        "signal": row["signal"],
                        "severity": severity,
                        "message": message,
                    }
                )

        return anomalies


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


def risk_all_data() -> list[dict]:
    states = ["Maharashtra", "Gujarat", "Tamil_Nadu", "Delhi", "UP"]
    results = []

    for s in states:
        score = float(np.random.uniform(30, 85))

        if score < 33:
            level = "GREEN"
        elif score < 66:
            level = "AMBER"
        else:
            level = "RED"

        results.append({
            "state": s,
            "risk_score": round(score, 2),
            "risk_level": level,
            "top_factors": ["demand", "anomaly"],
            "recommendation": "Monitor load closely"
        })

    return results


REGION_GROUPS = {
    "North": ["Delhi", "UP"],
    "West": ["Maharashtra", "Gujarat"],
    "South": ["Tamil_Nadu"],
}


def region_summary_data() -> list[dict]:
    forecast_rows = forecast_summary()
    risk_rows = risk_all_data()

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

        if avg_risk < 33:
            risk_level = "GREEN"
        elif avg_risk < 66:
            risk_level = "AMBER"
        else:
            risk_level = "RED"

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
    return risk_all_data()


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
                        "content": "You are GridFlow AI, an expert energy grid analyst. Answer in 2-3 sentences with real numbers and actionable insights."
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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
