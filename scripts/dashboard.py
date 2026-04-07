import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="GridFlow Energy Trading Terminal", layout="wide")

API_BASE = "http://127.0.0.1:8001"

st.markdown(
    """
    <style>
    :root {
        --bg-main: #0E1117;
        --neon-green: #00FFC8;
        --neon-red: #FF3131;
        --text-main: #E6EDF3;
        --card-bg: #151A24;
    }
    .stApp {
        background-color: var(--bg-main);
        color: var(--text-main);
    }
    .terminal-header {
        padding: 1rem 1.2rem;
        border: 1px solid #232A36;
        border-radius: 10px;
        background: linear-gradient(90deg, #121826 0%, #0E1117 100%);
        margin-bottom: 1rem;
    }
    .terminal-title {
        color: var(--neon-green);
        font-size: 1.6rem;
        font-weight: 700;
    }
    .terminal-subtitle {
        color: #9AA4B2;
        font-size: 0.92rem;
    }
    .section-wrap {
        border: 1px solid #232A36;
        border-radius: 10px;
        background: var(--card-bg);
        padding: 0.9rem;
        margin-bottom: 0.9rem;
    }
    .section-title {
        color: #C7D2E0;
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }
    .signal-card {
        border-radius: 8px;
        padding: 0.8rem;
        border: 1px solid #2A3342;
        text-align: center;
        min-height: 110px;
        background: #111722;
    }
    .signal-buy {
        border-color: var(--neon-green);
        box-shadow: 0 0 12px rgba(0, 255, 200, 0.15);
    }
    .signal-sell {
        border-color: var(--neon-red);
        box-shadow: 0 0 12px rgba(255, 49, 49, 0.15);
    }
    .signal-store {
        border-color: #D4AF37;
    }
    .signal-label {
        font-size: 0.78rem;
        color: #95A1B2;
        letter-spacing: 0.08em;
    }
    .signal-value {
        font-size: 1.35rem;
        font-weight: 700;
        margin-top: 0.2rem;
    }
    .buy-color { color: var(--neon-green); }
    .sell-color { color: var(--neon-red); }
    .store-color { color: #D4AF37; }
    .critical { color: var(--neon-red); font-weight: 700; }
    .healthy { color: var(--neon-green); font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "last_res" not in st.session_state:
    st.session_state["last_res"] = None

st.markdown(
    """
    <div class="terminal-header">
      <div class="terminal-title">GridFlow Pro Energy Trading Terminal</div>
      <div class="terminal-subtitle">Strategic Arbitrage Engine • Live Grid + Profitability Intelligence</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Trading Inputs")
    region = st.selectbox(
        "Region",
        ["Northern", "Western", "Southern", "Eastern", "North-Eastern"],
    )
    sim_hour = st.slider("Hour", 0, 23, 12)
    temp = st.slider("Temperature (C)", 10, 50, 32)
    is_festival = st.checkbox("Festival Mode")
    solar_capacity = st.number_input("Solar Capacity (MW)", min_value=0.0, value=12000.0)
    storage_soc = st.slider("Storage SOC (%)", 0, 100, 50)
    operating_cost = st.number_input("Operating Cost (INR/MWh)", min_value=0.0, value=3.25)
    capital_employed = st.number_input("Capital Employed (INR)", min_value=0.0, value=25000.0)
    wacc = st.slider("WACC", 0.00, 1.00, 0.10, 0.01)
    carbon_credit_price = st.number_input("Carbon Credit Price (INR/tCO2)", min_value=0.0, value=1500.0)

    run = st.button("Run Live Analysis", use_container_width=True)

if run:
    payload = {
        "region": region,
        "temp": temp,
        "is_festival": is_festival,
        "solar_capacity": solar_capacity,
        "sim_hour": sim_hour,
        "storage_soc": storage_soc,
        "operating_cost_per_mwh": operating_cost,
        "capital_employed": capital_employed,
        "wacc": wacc,
        "carbon_credit_price": carbon_credit_price,
    }
    try:
        response = requests.post(f"{API_BASE}/api/v1/analyze", json=payload, timeout=10)
        response.raise_for_status()
        st.session_state["last_res"] = response.json()
    except requests.RequestException:
        st.error("Backend unavailable. Start FastAPI with `python scripts/app.py`.")

last_res = st.session_state["last_res"]

# 1) Live Grid Telemetry
st.markdown('<div class="section-wrap"><div class="section-title">1. Live Grid Telemetry</div>', unsafe_allow_html=True)
if last_res:
    metrics = last_res["metrics"]
    economics = last_res["economics"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Demand (MW)", f"{metrics['demand_mw']:,.2f}")
    c2.metric("Solar (MW)", f"{metrics['solar_mw']:,.2f}")
    c3.metric("Net Load (MW)", f"{metrics['net_load_mw']:,.2f}")
    c4.metric("Grid Health", f"{metrics['health_score']:.2f}")
    c5.metric("Spot Price", f"INR {economics['spot_price_inr_per_mwh']:.2f}")

    health_class = "critical" if metrics["health_score"] < 60 else "healthy"
    st.markdown(
        f"<div>Grid Status: <span class='{health_class}'>{last_res['decision']['risk']}</span></div>",
        unsafe_allow_html=True,
    )
else:
    st.info("Run analysis to stream live telemetry.")
st.markdown("</div>", unsafe_allow_html=True)

# 2) AI Arbitrage Recommendations (Buy/Sell/Store cards)
st.markdown(
    '<div class="section-wrap"><div class="section-title">2. AI Arbitrage Recommendations</div>',
    unsafe_allow_html=True,
)
if last_res:
    signal = last_res["decision"]["signal"]
    rationale = last_res["decision"]["rationale"]
    buy_class = "signal-buy" if signal == "BUY" else ""
    sell_class = "signal-sell" if signal == "SELL" else ""
    store_class = "signal-store" if signal == "STORE" else ""

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(
            f"""
            <div class="signal-card {buy_class}">
                <div class="signal-label">BUY</div>
                <div class="signal-value buy-color">{"ACTIVE" if signal == "BUY" else "STANDBY"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f"""
            <div class="signal-card {sell_class}">
                <div class="signal-label">SELL</div>
                <div class="signal-value sell-color">{"ACTIVE" if signal == "SELL" else "STANDBY"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f"""
            <div class="signal-card {store_class}">
                <div class="signal-label">STORE</div>
                <div class="signal-value store-color">{"ACTIVE" if signal == "STORE" else "STANDBY"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.caption(f"Signal Rationale: {rationale}")
else:
    st.info("Recommendation cards activate after a run.")
st.markdown("</div>", unsafe_allow_html=True)

# 3) Sustainability Impact (CO2 Offset)
st.markdown(
    '<div class="section-wrap"><div class="section-title">3. Sustainability Impact (CO2 Offset)</div>',
    unsafe_allow_html=True,
)
if last_res:
    eco = last_res["economics"]
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("CO2 Avoided (tCO2)", f"{eco['carbon_avoided_tco2']:.4f}")
    s2.metric("Carbon Credit Savings", f"INR {eco['carbon_credit_savings_inr']:.2f}")
    s3.metric("EVA (INR)", f"{eco['eva_inr']:.2f}")
    s4.metric("NOPAT (INR)", f"{eco['nopat_inr']:.2f}")
else:
    st.info("Run analysis to view sustainability impact.")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="section-wrap"><div class="section-title">Stress vs Profit (Real-Time)</div>', unsafe_allow_html=True)
try:
    history_response = requests.get(f"{API_BASE}/api/v1/history", params={"limit": 500}, timeout=10)
    history_response.raise_for_status()
    raw = history_response.json()
    if raw:
        df = pd.DataFrame(raw)
        df["stress"] = 100 - pd.to_numeric(df["health"], errors="coerce")
        df["eva"] = pd.to_numeric(df["eva"], errors="coerce")
        fig = px.scatter(
            df,
            x="stress",
            y="eva",
            color="signal",
            size="price_val",
            hover_data=["region", "hour", "health"],
            color_discrete_map={"BUY": "#00FFC8", "SELL": "#FF3131", "STORE": "#D4AF37"},
            template="plotly_dark",
            labels={"stress": "Grid Stress (100 - health)", "eva": "Profit (EVA, INR)"},
        )
        fig.update_layout(
            paper_bgcolor="#151A24",
            plot_bgcolor="#0E1117",
            font_color="#E6EDF3",
            legend_title_text="Signal",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df.head(12), use_container_width=True)
    else:
        st.info("No history yet. Run live analysis to seed chart data.")
except requests.RequestException:
    st.error("Unable to load history for Stress vs Profit chart.")
st.markdown("</div>", unsafe_allow_html=True)