# app/views/strategic_insights.py
import streamlit as st
import pandas as pd
from backend import strategic_insights as si

def show_strategic_insights(st, user_prefs):
    st.header("📈 Strategic Insights")
    # Assume stock_data and news_verdicts are available from session or backend
    stock_data = st.session_state.get("stock_data_df")
    news_verdicts = st.session_state.get("news_verdicts", {})
    if stock_data is None or not isinstance(stock_data, pd.DataFrame):
        st.info("No stock data available. Please run a screener or analysis first.")
        return

    with st.expander("GARP Strategy (Growth at a Reasonable Price)"):
        if st.button("Run GARP Strategy"):
            result = si.run_garp_strategy(stock_data)
            st.dataframe(result)

    with st.expander("Fallen Angels"):
        if st.button("Run Fallen Angels"):
            result = si.run_fallen_angels(stock_data)
            st.dataframe(result)

    with st.expander("Value Trap Detector"):
        if st.button("Run Value Trap Detector"):
            result = si.run_value_trap_filter(stock_data, news_verdicts)
            st.dataframe(result)

    with st.expander("Momentum + Quality Combo"):
        if st.button("Run Momentum + Quality Combo"):
            result = si.run_momentum_quality_combo(stock_data)
            st.dataframe(result)

    with st.expander("Low Volatility Anomaly"):
        if st.button("Run Low Volatility Anomaly"):
            result = si.run_low_volatility_anomaly(stock_data, news_verdicts)
            st.dataframe(result)
