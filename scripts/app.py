from fastapi import FastAPI, HTTPException
import pandas as pd
import joblib
import os
import numpy as np

app = FastAPI()

# Absolute Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "cleaned_demand.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "gridflow_model.pkl")

# --- LOAD ONCE (Saves Memory & Time) ---
# We load them outside the functions so they only load when the server starts
if os.path.exists(DATA_PATH) and os.path.exists(MODEL_PATH):
    GLOBAL_DF = pd.read_csv(DATA_PATH)
    GLOBAL_MODEL = joblib.load(MODEL_PATH)
else:
    GLOBAL_DF = None
    GLOBAL_MODEL = None

COST_PER_UNIT = {
    "transformers": 500000, 
    "heavy_cables_km": 25000,
    "insulators": 500
}

@app.get("/")
def read_root():
    return {
        "status": "Online", 
        "engine": "GridFlow AI", 
        "data_ready": GLOBAL_DF is not None, 
        "model_ready": GLOBAL_MODEL is not None
    }

@app.get("/api/v1/pro-analysis")
def get_advanced_analysis():
    if GLOBAL_DF is None or GLOBAL_MODEL is None:
        raise HTTPException(status_code=500, detail="Server not fully initialized. Check CSV and PKL files.")

    # 1. AI Base Prediction
    last_3_days = GLOBAL_DF['demand_mw'].tail(3).values.reshape(1, -1)
    base_prediction = GLOBAL_MODEL.predict(last_3_days)[0]

    # 2. Risk & Financial Logic
    peak_scenario = base_prediction * 1.20 
    total_budget = (
        (base_prediction * 0.05 * COST_PER_UNIT["transformers"]) +
        (base_prediction * 1.2 * COST_PER_UNIT["heavy_cables_km"])
    )

    # 3. Reliability logic
    actual_yesterday = GLOBAL_DF['demand_mw'].iloc[-1]
    predicted_yesterday = GLOBAL_DF['demand_mw'].iloc[-2]
    accuracy = 100 - abs((actual_yesterday - predicted_yesterday) / actual_yesterday) * 100

    return {
        "forecast": {
            "standard_mw": round(base_prediction, 2),
            "emergency_peak_mw": round(peak_scenario, 2)
        },
        "financials": {
            "estimated_procurement_cost_inr": round(total_budget, 2)
        },
        "system_health": {
            "prediction_accuracy": f"{round(accuracy, 2)}%",
            "status": "Stable" if accuracy > 90 else "Reviewing Patterns"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)