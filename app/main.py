import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import streamlit as st
from config.ticker_lists import TICKER_TO_NAME
from backend.data_fetcher import get_ticker_data
import pandas as pd
from datetime import datetime
import logging
import json
import importlib

# --- CONFIGURATION (MUST BE AT THE TOP) ---
st.set_page_config(page_title="StockMatrix", layout="wide")

# --- Backend & NLP Module Imports ---
from backend import (
    technical_analysis as ta_mod,
    fundamental_analysis as fa_mod,
    sentiment_analysis as sentiment_mod,
    news_risk_analyzer as news_mod,
    leaderboard_engine,
    screener_engine,
    market_selector
)

# --- Persistent User Preferences ---
PREFS_KEY = "stockmatrix_user_prefs"
def load_user_prefs():
    try:
        if PREFS_KEY in st.session_state:
            return st.session_state[PREFS_KEY]
        prefs = st.query_params.get(PREFS_KEY, [None])[0]
        if prefs:
            return json.loads(prefs)
    except Exception:
        pass
    return {}

def save_user_prefs(prefs):
    st.session_state[PREFS_KEY] = prefs
    try:
        st.experimental_set_query_params(**{PREFS_KEY: json.dumps(prefs)})
    except Exception:
        pass

user_prefs = load_user_prefs()

# --- Function to load external CSS ---
def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"CSS file not found: {file_name}. Please make sure 'app/style.css' exists.")

# Apply the external CSS file
load_css("app/style.css")

# --- FONT & ICON INJECTION ---
st.markdown("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Poppins:wght@900&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />
""", unsafe_allow_html=True)

st.title("StockMatrix")

# --- Session State Initialization ---
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = "welcome"

# --- Sidebar ---
with st.sidebar:
    st.markdown("<h2>Watchlist</h2>", unsafe_allow_html=True)
    watchlist = user_prefs.get("watchlist", [])
    
    for ticker in watchlist:
        if st.button(ticker, key=f"watchlist_{ticker}", use_container_width=True):
            st.session_state["run_analysis_ticker"] = ticker
            st.session_state["chat_mode"] = "run_analysis"
            st.rerun()

    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
    add_ticker = st.text_input("Add Ticker", key="add_watchlist", placeholder="Add Ticker")
    if st.button("Add", key="add_watchlist_btn", use_container_width=True):
        if add_ticker and add_ticker.upper() not in watchlist:
            watchlist.append(add_ticker.upper())
            user_prefs["watchlist"] = watchlist
            save_user_prefs(user_prefs)
            st.success(f"Added {add_ticker.upper()}")
            st.rerun()

    if watchlist:
        remove_selection = st.selectbox("Remove Ticker", ["-"] + watchlist, key="remove_watchlist")
        if st.button("Remove", key="remove_watchlist_btn", type="secondary", use_container_width=True):
            if remove_selection != "-":
                watchlist.remove(remove_selection)
                user_prefs["watchlist"] = watchlist
                save_user_prefs(user_prefs)
                st.rerun()
    
    st.markdown('<hr style="margin: 2rem 0; border-color: var(--border-color);">', unsafe_allow_html=True)

    st.markdown("<h2>Navigation</h2>", unsafe_allow_html=True)
    if st.button("📈 Strategic Insights"):
        st.session_state.chat_mode = "strategic_insights"
        st.rerun()
    if st.button("🚀 Backtesting Engine"):
        st.session_state.chat_mode = "backtesting"
        st.rerun()
    if st.button("🌌 3D Market Visualizer"):
        st.session_state.chat_mode = "market_visualizer"
        st.rerun()

    st.markdown('<hr style="margin: 2rem 0; border-color: var(--border-color);">', unsafe_allow_html=True)

    st.markdown("<h2>Settings & Accessibility</h2>", unsafe_allow_html=True)
    if st.button("❓ Help / Quick Tour"):
        st.session_state.chat_mode = "onboarding"
        st.rerun()


# --- Main Content ---
if st.session_state.chat_mode == "welcome":
    st.markdown('<div class="welcome-card">', unsafe_allow_html=True)
    st.markdown("<h2>Welcome Assistant</h2>", unsafe_allow_html=True)
    st.markdown("<p>What can I help you with today?</p>", unsafe_allow_html=True)
    
    st.empty()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="action-card">
            <span class="material-symbols-outlined">query_stats</span>
            <h3>Run Analysis</h3>
            <p>Perform a deep-dive analysis on a specific stock or market sector.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Go to Analysis", key="welcome_analysis", use_container_width=True):
            st.session_state.chat_mode = "run_analysis"
            st.rerun()

    with col2:
        st.markdown("""
        <div class="action-card">
            <span class="material-symbols-outlined">receipt_long</span>
            <h3>Generate a Report</h3>
            <p>Create a comprehensive, shareable report based on your analysis.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Go to Reports", key="welcome_report", use_container_width=True):
            st.session_state.chat_mode = "report"
            st.rerun()

    with col3:
        st.markdown("""
        <div class="action-card">
            <span class="material-symbols-outlined">lightbulb</span>
            <h3>Get Insights</h3>
            <p>Discover trends and anomalies using our AI-powered insights engine.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Go to Insights", key="welcome_insights", use_container_width=True):
            st.session_state.chat_mode = "screener"
            st.rerun()

    st.empty()
    user_input = st.chat_input("Or, type a command...")
    if user_input:
        st.info(f"Command received: {user_input}")

    st.markdown('</div>', unsafe_allow_html=True)

else:
    from app.views.routing import get_view
    view_func = get_view(st.session_state.get("chat_mode"))
    view_func(st, user_prefs)
