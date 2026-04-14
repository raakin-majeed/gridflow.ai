from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def ensure_package(import_name: str, pip_name: str) -> None:
    try:
        __import__(import_name)
    except ImportError:
        print(f"Installing missing package: {pip_name}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])


ensure_package("prophet", "prophet")
ensure_package("joblib", "joblib")

import joblib
import numpy as np
import pandas as pd
from prophet import Prophet


ROOT_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT_DIR / "data" / "dataset_tk.csv"
MODELS_DIR = ROOT_DIR / "models"
FORECASTS_DIR = ROOT_DIR / "data" / "forecasts"


def resolve_state_column(dataframe: pd.DataFrame, preferred_name: str) -> str:
    if preferred_name in dataframe.columns:
        return preferred_name

    aliases = {
        "UP": [
            "UP",
            "Uttar Pradesh",
            "UTTAR PRADESH",
            "uttar pradesh",
        ],
        "Tamil Nadu": ["Tamil Nadu", "TAMIL NADU", "TamilNadu"],
        "Maharashtra": ["Maharashtra", "MAHARASHTRA"],
        "Gujarat": ["Gujarat", "GUJARAT"],
        "Delhi": ["Delhi", "DELHI", "NCT of Delhi", "NCT DELHI"],
    }

    if preferred_name in aliases:
        for alias in aliases[preferred_name]:
            if alias in dataframe.columns:
                return alias

    raise KeyError(f"Could not find a column for state: {preferred_name}")


def prepare_data() -> pd.DataFrame:
    df = pd.read_csv(DATASET_PATH)
    df = df.rename(columns={"Unnamed: 0": "date"})
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")

    if "date" not in df.columns:
        raise ValueError("Expected a date column after renaming 'Unnamed: 0'.")

    state_columns = [column for column in df.columns if column != "date"]
    df[state_columns] = df[state_columns].apply(pd.to_numeric, errors="coerce")

    key_states = {
        "Maharashtra": resolve_state_column(df, "Maharashtra"),
        "Gujarat": resolve_state_column(df, "Gujarat"),
        "Tamil Nadu": resolve_state_column(df, "Tamil Nadu"),
        "Delhi": resolve_state_column(df, "Delhi"),
        "UP": resolve_state_column(df, "UP"),
    }

    df["total_demand"] = df[state_columns].sum(axis=1)

    selected_columns = ["date", "total_demand", *key_states.values()]
    cleaned = df[selected_columns].copy()
    cleaned = cleaned.rename(columns={v: k for k, v in key_states.items()})
    cleaned = cleaned.dropna().sort_values("date").reset_index(drop=True)
    return cleaned


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def train_and_forecast(cleaned_df: pd.DataFrame) -> list[tuple[str, float, float]]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    FORECASTS_DIR.mkdir(parents=True, exist_ok=True)

    evaluation_report: list[tuple[str, float, float]] = []
    series_names = [
        "total_demand",
        "Maharashtra",
        "Gujarat",
        "Tamil Nadu",
        "Delhi",
        "UP",
    ]

    for series_name in series_names:
        series_df = cleaned_df[["date", series_name]].rename(
            columns={"date": "ds", series_name: "y"}
        )

        if len(series_df) < 60:
            raise ValueError(
                f"Not enough rows to train and evaluate '{series_name}'. Need >= 60."
            )

        train_df = series_df.iloc[:-30].copy()
        test_df = series_df.iloc[-30:].copy()

        eval_model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
        )
        eval_model.add_country_holidays(country_name="IN")
        eval_model.fit(train_df)

        eval_forecast = eval_model.predict(test_df[["ds"]])[["ds", "yhat"]]
        eval_merged = test_df.merge(eval_forecast, on="ds", how="left")

        model_mae = mae(eval_merged["y"].to_numpy(), eval_merged["yhat"].to_numpy())
        model_rmse = rmse(eval_merged["y"].to_numpy(), eval_merged["yhat"].to_numpy())
        evaluation_report.append((series_name, model_mae, model_rmse))

        final_model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
        )
        final_model.add_country_holidays(country_name="IN")
        final_model.fit(series_df)

        future_90 = final_model.make_future_dataframe(periods=90)
        forecast_90 = final_model.predict(future_90)[
            ["ds", "yhat", "yhat_lower", "yhat_upper"]
        ]
        future_only = forecast_90[forecast_90["ds"] > series_df["ds"].max()].copy()

        forecast_path = FORECASTS_DIR / f"{series_name}_forecast.csv"
        actuals_path = FORECASTS_DIR / f"{series_name}_actuals.csv"
        model_path = MODELS_DIR / f"{series_name}_prophet.pkl"

        future_only.to_csv(forecast_path, index=False)
        series_df.to_csv(actuals_path, index=False)
        joblib.dump(final_model, model_path)

    return evaluation_report


def main() -> None:
    cleaned_df = prepare_data()
    report = train_and_forecast(cleaned_df)
    print("=== GridFlow Forecast Evaluation Report ===")
    for series_name, model_mae, model_rmse in report:
        print(
            f"Series: {series_name} | MAE: {model_mae:.4f} | RMSE: {model_rmse:.4f} | MU = Million Units"
        )


if __name__ == "__main__":
    main()
