import math
import os
import random
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import uvicorn
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

# Vercel/Postgres-ready database URL. Falls back to local SQLite for dev.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///../data/gridflow.db")
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
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
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
    return brain.compute(
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


@app.get("/api/v1/states")
def states() -> list[dict]:
    states_path = DATA_DIR / "long_data_.csv"
    if not states_path.exists():
        raise HTTPException(status_code=404, detail="State data file not found.")

    df = pd.read_csv(states_path)
    required_columns = {"States", "Regions", "latitude", "longitude"}
    if not required_columns.issubset(df.columns):
        raise HTTPException(status_code=500, detail="State data columns are missing.")

    unique_states = (
        df[["States", "Regions", "latitude", "longitude"]]
        .dropna(subset=["States", "Regions", "latitude", "longitude"])
        .drop_duplicates(subset=["States"])
    )

    return [
        {
            "state": row["States"],
            "region": row["Regions"],
            "lat": float(row["latitude"]),
            "lon": float(row["longitude"]),
        }
        for _, row in unique_states.iterrows()
    ]


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
