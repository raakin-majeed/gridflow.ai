import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(page_title="GridFlow AI Ops", layout="wide")

st.title("⚡ GridFlow.ai | Maharashtra Smart Grid")
st.sidebar.header("System Control Room")

# --- Backend Connection ---
API_URL = "http://127.0.0.1:8001/api/v1/full-analysis"

def get_data():
    try:
        response = requests.get(API_URL)
        return response.json()
    except:
        return None

# --- Dashboard Layout ---
data = get_data()

if data:
    # 1. Top Row Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Adjusted Load", f"{data['grid_metrics']['weather_adjusted_mw']} MW", delta=f"{data['grid_metrics']['ambient_temp_c']}°C")
    col2.metric("CO2 Footprint", f"{data['environment']['est_hourly_co2_kg']} kg")
    col3.metric("System Health", f"{data['system_status']['health_score']}%")

    # 2. Main Content
    st.divider()
    
    # Simulate a historical trend for the chart
    st.subheader("Demand Forecasting Trend")
    chart_data = pd.DataFrame({
        'Time': [f"T-{i}h" for i in range(5, -1, -1)],
        'Load (MW)': [data['grid_metrics']['base_demand_mw'] + (i * 2) for i in range(6)]
    })
    st.line_chart(chart_data.set_index('Time'))

    # 3. Alerts
    if data['system_status']['alerts'] != "Normal":
        for alert in data['system_status']['alerts']:
            st.error(alert)
    else:
        st.success("✅ All grid systems operating within safe parameters.")

else:
    st.warning("⚠️ Backend server not detected. Please run 'python scripts/app.py' first.")

if st.sidebar.button('Refresh Data'):
    st.rerun()