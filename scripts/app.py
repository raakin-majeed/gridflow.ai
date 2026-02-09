from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import numpy as np
import os

app = FastAPI(title="GridFlow AI Engine")

# Load the trained model
MODEL_PATH = "models/gridflow_model.pkl"
if os.path.exists(MODEL_PATH):
    model = joblib.load(MODEL_PATH)
else:
    model = None

class PredictionRequest(BaseModel):
    # User sends the last 3 days of grid load/material usage
    history: list[float]

@app.post("/predict")
async def predict(data: PredictionRequest):
    if model is None:
        raise HTTPException(status_code=500, detail="Model file not found. Run train_model.py first.")
    
    if len(data.history) != 3:
        raise HTTPException(status_code=400, detail="Please provide exactly 3 historical data points.")

    # Convert input to the format the AI expects
    input_array = np.array(data.history).reshape(1, -1)
    
    # Generate prediction
    prediction = model.predict(input_array)[0]
    
    return {
        "predicted_demand": round(float(prediction), 2),
        "unit": "MW / Units",
        "algorithm": "Random Forest Regressor"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)