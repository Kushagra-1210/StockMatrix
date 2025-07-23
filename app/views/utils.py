# Utility functions and session state helpers for StockMatrix

import streamlit as st

def reset_analysis_data():
    for key in ["technicals", "fundamentals", "perception", "risk", "final_score", "final_verdict", "final_weights"]:
        if key in st.session_state:
            st.session_state[key] = None
