from fastapi import FastAPI, HTTPException
import pandas as pd
import joblib
import os
import numpy as np
import random

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


# --- New Feature: Weather Intelligence ---
def get_mock_weather():
    # Simulate a realistic Maharashtra afternoon temperature
    temp = random.uniform(28.0, 38.0) 
    condition = "Heatwave" if temp > 34 else "Normal"
    return {"temp_celsius": round(temp, 1), "condition": condition}

@app.get("/api/v1/weather-impact")
def get_weather_impact():
    """Simulates how temperature spikes in Maharashtra affect the grid"""
    # 1. Simulate a random temperature for Maharashtra
    temp = random.uniform(28.0, 40.0) 
    
    # 2. Get the base prediction from our AI
    base_analysis = get_advanced_analysis()
    base_mw = base_analysis['forecast']['standard_mw']
    
    # 3. Apply Thermal Load Logic: +3% demand for every degree above 30°C
    impact_multiplier = 1.0
    if temp > 30:
        impact_multiplier = 1 + ((temp - 30) * 0.03)
    
    adjusted_mw = base_mw * impact_multiplier
    
    return {
        "metadata": {
            "location": "Maharashtra",
            "ambient_temp_c": round(temp, 1),
            "status": "Heatwave Warning" if temp > 35 else "Normal"
        },
        "analysis": {
            "base_demand_mw": round(base_mw, 2),
            "weather_adjusted_demand_mw": round(adjusted_mw, 2),
            "thermal_load_increase_percent": f"{round((impact_multiplier - 1) * 100, 1)}%"
        }
    }

# --- Sustainability Metrics (India Grid Specific) ---
# Average CO2 emissions in India: ~0.82 kg CO2 per kWh (approx. 820 kg per MWh)
EMISSION_FACTOR_CO2_PER_MWH = 820 

@app.get("/api/v1/sustainability")
def get_sustainability_impact():
    """Calculates the environmental cost of the forecasted demand"""
    base_analysis = get_advanced_analysis()
    forecasted_mw = base_analysis['forecast']['standard_mw']
    
    # 1. Calculate CO2 (Assuming 1 hour of this load)
    # 1 MW for 1 hour = 1 MWh
    total_co2_kg = forecasted_mw * EMISSION_FACTOR_CO2_PER_MWH
    
    # 2. Real-world equivalents (to make data understandable)
    # 1 mature tree absorbs ~21kg of CO2 per year
    trees_needed = total_co2_kg / 21
    
    return {
        "carbon_footprint": {
            "hourly_co2_emissions_kg": round(total_co2_kg, 2),
            "equivalent_trees_to_offset": round(trees_needed, 0)
        },
        "energy_mix_estimate": {
            "thermal_coal": "70%",
            "renewables": "22%",
            "other": "8%"
        },
        "recommendation": "High Emissions. Suggest triggering Demand Response protocols." if total_co2_kg > 350000 else "Stable Emissions."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)


