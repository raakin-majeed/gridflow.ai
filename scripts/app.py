from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import joblib
import os
import numpy as np

app = FastAPI()

# Absolute Paths to avoid "File Not Found" errors
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "cleaned_demand.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "gridflow_model.pkl")

# --- HOME ROUTE (Test this first!) ---
@app.get("/")
def read_root():
    return {
        "status": "Online", 
        "engine": "GridFlow AI", 
        "data_check": os.path.exists(DATA_PATH),
        "model_check": os.path.exists(MODEL_PATH)
    }

# --- THE FUNCTIONAL BACKEND ---
@app.get("/api/v1/inventory-needs")
def get_inventory_needs():
    if not os.path.exists(DATA_PATH) or not os.path.exists(MODEL_PATH):
        raise HTTPException(status_code=404, detail=f"Files missing. Data: {os.path.exists(DATA_PATH)}, Model: {os.path.exists(MODEL_PATH)}")

    # 1. Load data and model
    df = pd.read_csv(DATA_PATH)
    model = joblib.load(MODEL_PATH)

    # 2. Extract last 3 days for the "Brain"
    last_3_days = df['demand_mw'].tail(3).values.reshape(1, -1)
    
    # 3. AI Prediction
    predicted_mw = model.predict(last_3_days)[0]

    # 4. Logic: Map MW to physical inventory
    inventory = {
        "transformers": round(predicted_mw * 0.05, 2),
        "heavy_cables_km": round(predicted_mw * 1.2, 2),
        "insulators": round(predicted_mw * 15.0, 2)
    }

    return {
        "forecasted_load_mw": round(float(predicted_mw), 2),
        "inventory_required": inventory,
        "source": "POSOCO Maharashtra Dataset"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)