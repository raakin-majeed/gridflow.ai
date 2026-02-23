import streamlit as st
import requests
import pandas as pd
import datetime

st.set_page_config(page_title="GridFlow AI Ops", layout="wide")

# --- Initialize Memory (Session State) ---
# This keeps the data from disappearing when the page refreshes
if 'history' not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=['Time', 'Load'])

st.title("⚡ GridFlow.ai | Real-Time Operations")
st.sidebar.header("Control Panel")

API_URL = "http://127.0.0.1:8001/api/v1/full-analysis"

def fetch_data():
    try:
        response = requests.get(API_URL)
        return response.json()
    except Exception as e:
        st.sidebar.error(f"Connection Error: {e}")
        return None

# --- Main App Logic ---
data = fetch_data()

if data and 'grid_metrics' in data:
    # 1. Update Memory
    new_entry = {
        'Time': datetime.datetime.now().strftime("%H:%M:%S"),
        'Load': data['grid_metrics']['weather_adjusted_mw']
    }
    
    # Add new data to the history table
    st.session_state.history = pd.concat([
        st.session_state.history, 
        pd.DataFrame([new_entry])
    ]).tail(20) # Keep only the last 20 points

    # 2. Display Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Current Demand", f"{data['grid_metrics']['weather_adjusted_mw']} MW", 
                delta=f"{data['grid_metrics']['ambient_temp_c']}°C")
    col2.metric("CO2 Emissions", f"{data['environment']['est_hourly_co2_kg']} kg")
    col3.metric("Grid Health", f"{data['system_status']['health_score']}%")

    st.divider()

    # 3. The Dynamic Graph
    st.subheader("Live Grid Load Monitoring (Moving Average)")
    if not st.session_state.history.empty:
        # We use a line chart that updates every time you hit 'Refresh'
        st.line_chart(st.session_state.history.set_index('Time'))
    
    # 4. Critical Alerts Area
    st.subheader("Active Grid Alerts")
    alerts = data['system_status']['alerts']
    if "✅ Grid operating normally" in alerts:
        st.success(alerts[0])
    else:
        for a in alerts:
            st.warning(a)

else:
    st.error("Waiting for Backend... ensure 'python scripts/app.py' is running on port 8001.")

# 5. Manual Trigger
if st.button('🔄 Update Forecast'):
    st.rerun()