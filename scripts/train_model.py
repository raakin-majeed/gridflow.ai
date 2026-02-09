import pandas as pd
import joblib
import os
from sklearn.ensemble import RandomForestRegressor

def train_demand_predictor():
    # 1. Paths
    os.makedirs('models', exist_ok=True)
    data_path = 'data/cleaned_demand.csv'
    model_path = 'models/gridflow_model.pkl'

    if not os.path.exists(data_path):
        print("❌ Error: cleaned_demand.csv not found. Run process_data.py first!")
        return

    # 2. Load Data
    df = pd.read_csv(data_path)
    
    # 3. Feature Engineering (Time-Series)
    # We teach the AI to look at the last 3 days to predict the next day
    df['lag_1'] = df['demand_mw'].shift(1)
    df['lag_2'] = df['demand_mw'].shift(2)
    df['lag_3'] = df['demand_mw'].shift(3)
    df = df.dropna()

    X = df[['lag_1', 'lag_2', 'lag_3']]
    y = df['demand_mw']

    # 4. Train Random Forest (Industry Standard for robust predictions)
    print("🧠 Training AI Model on Indian Grid patterns...")
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)

    # 5. Save the "Brain"
    joblib.dump(model, model_path)
    print(f"✅ SUCCESS: AI model trained and saved to {model_path}")

if __name__ == "__main__":
    train_demand_predictor()