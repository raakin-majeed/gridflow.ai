import kagglehub
import pandas as pd
import os

def clean_indian_grid_data():
    # 1. Setup paths
    os.makedirs('data', exist_ok=True)
    
    # 2. Download from Kaggle
    print("📥 Downloading POSOCO State-wise Power Data...")
    path = kagglehub.dataset_download("twinkle0705/state-wise-power-consumption-in-india")
    
    # 3. Find and Load the CSV
    csv_file = [f for f in os.listdir(path) if f.endswith('.csv')][0]
    df = pd.read_csv(os.path.join(path, csv_file))
    
    # 4. Data Transformation (The "Proper" Logic)
    # The first column contains the state names
    df.rename(columns={df.columns[0]: 'date'}, inplace=True)
    df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date')
    
    # Focus on Maharashtra (The industrial heartbeat of the grid)
    if 'Maharashtra' in df.columns:
        # We clean it to: Date and Demand (Quantity)
        final_df = df[['date', 'Maharashtra']].copy()
        final_df.columns = ['date', 'demand_mw']
        
        # Save for our AI training
        final_df.to_csv('data/cleaned_demand.csv', index=False)
        print("✅ SUCCESS: Data saved to data/cleaned_demand.csv")
    else:
        print("❌ Error: Maharashtra column missing.")

if __name__ == "__main__":
    clean_indian_grid_data()