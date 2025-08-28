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
# This is a placeholder for your NLP logic if you have one
# from nlp.chat_router import handle_chat_command 

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

# --- FONT & ICON INJECTION ---
st.markdown("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Poppins:wght@900&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />
""", unsafe_allow_html=True)


# --- PROFESSIONAL DASHBOARD CSS ---
css = '''
<style>
    /* --- CSS Variables for Theming --- */
    :root {
      --primary-background: #1A1B25;
      --sidebar-background: #13141B;
      --card-background: #24263D;
      --primary-text: #EAEBFF;
      --secondary-text: #9D9DBC;
      --border-color: #333652;
      --primary-accent-start: #5D5FEF;
      --primary-accent-end: #7B61FF;
      --destructive-start: #D32F2F;
      --destructive-end: #E57372;
    }

    /* --- Base Body & App Styling --- */
    body, .stApp {
        background-color: var(--primary-background);
        color: var(--primary-text);
        font-family: 'Inter', sans-serif;
    }
    
    /* --- Header/Title --- */
    .stApp > header {
        background-color: transparent;
    }
    h1 {
        font-family: 'Poppins', sans-serif;
        font-size: 2.5rem;
        font-weight: 900;
        letter-spacing: 2px;
        text-align: center;
        padding-top: 1rem;
        padding-bottom: 1rem;
    }

    /* --- Sidebar Styling --- */
    .stSidebar {
        background-color: var(--sidebar-background);
        border-right: 1px solid var(--border-color);
    }
    .stSidebar h2 {
        color: var(--secondary-text);
        text-transform: uppercase;
        font-size: 0.9rem;
        font-weight: 700;
    }
    .stSidebar .stButton button {
        background-color: transparent;
        color: var(--primary-text);
        font-weight: 600;
        text-align: left;
        padding: 0.75rem;
        border-radius: 8px;
        transition: background-color 0.2s, transform 0.2s;
        width: 100%;
    }
    .stSidebar .stButton button:hover {
        background-color: rgba(255, 255, 255, 0.05);
        transform: translateX(2px);
    }
    /* Special "Add" button in sidebar */
    .stSidebar .stButton:has(button:not(:has(span))) button {
         background: linear-gradient(90deg, var(--primary-accent-start), var(--primary-accent-end));
    }
    .stSidebar .stButton button:not(:has(span)):hover {
        box-shadow: 0 0 15px 0 var(--primary-accent-end);
    }
    .stSidebar .stButton:has(button[kind="secondary"]) button {
        background: linear-gradient(90deg, var(--destructive-start), var(--destructive-end));
    }

    /* --- Main Content Area --- */
    .main .block-container {
        padding-top: 2rem;
    }
    
    /* --- Welcome Assistant Card --- */
    .welcome-card {
        background-color: var(--card-background);
        padding: 3rem;
        border-radius: 12px;
        border: 1px solid var(--border-color);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        max-width: 64rem;
        margin: auto;
    }
    .welcome-card h2 {
        font-size: 2rem;
        font-weight: 700;
        text-align: center;
    }
    .welcome-card > div > p {
        color: var(--secondary-text);
        text-align: center;
    }

    /* --- Action Cards --- */
    .action-card {
        padding: 1.5rem;
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        text-align: center;
        transition: background-color 0.2s;
        border: 1px solid transparent;
        margin-bottom: 1rem;
    }
    .action-card:hover {
        background-color: rgba(255, 255, 255, 0.1);
        border-color: var(--border-color);
    }
    .action-card .material-symbols-outlined {
        font-size: 3rem;
        color: var(--primary-accent-start);
    }
    .action-card h3 {
        font-weight: 700;
        font-size: 1.125rem;
        color: var(--primary-text);
    }
    .action-card p {
        color: var(--secondary-text);
        font-size: 0.9rem;
    }

    /* --- Chat Input --- */
    .stChatInput {
        background-color: var(--primary-background);
    }
    .stChatInput > div > input {
        background-color: var(--primary-background);
        border: 1px solid var(--border-color);
        border-radius: 8px 0 0 8px;
    }
    .stChatInput button {
        background: linear-gradient(90deg, var(--primary-accent-start), var(--primary-accent-end));
        border-radius: 0 8px 8px 0;
    }
</style>
'''
st.markdown(css, unsafe_allow_html=True)
st.title("StockMatrix")

# --- Session State Initialization ---
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = "welcome"

# --- Sidebar ---
with st.sidebar:
    st.markdown("## Watchlist")
    watchlist = user_prefs.get("watchlist", [])
    for ticker in watchlist:
        company_name = TICKER_TO_NAME.get(ticker.upper(), "Unknown Company")
        label = f"{ticker} - {company_name}"
        if st.button(label, key=f"watchlist_{ticker}"):
            st.session_state["run_analysis_ticker"] = ticker
            st.session_state["chat_mode"] = "run_analysis"
            st.rerun()

    add_ticker = st.text_input("Add Ticker to Watchlist", "", key="add_watchlist")
    if st.button("Add", key="add_watchlist_btn"):
        if add_ticker and add_ticker.upper() not in watchlist:
            watchlist.append(add_ticker.upper())
            user_prefs["watchlist"] = watchlist
            save_user_prefs(user_prefs)
            st.success(f"Added {add_ticker.upper()}")
            st.rerun()

    if watchlist:
        remove_selection = st.selectbox("Remove from Watchlist", ["-"] + watchlist, key="remove_watchlist")
        if st.button("Remove", key="remove_watchlist_btn", type="secondary"):
            if remove_selection != "-":
                watchlist.remove(remove_selection)
                user_prefs["watchlist"] = watchlist
                save_user_prefs(user_prefs)
                st.rerun()

    st.markdown("## Navigation")
    if st.button("📈 Strategic Insights"):
        st.session_state.chat_mode = "strategic_insights"
        st.rerun()
    if st.button("🚀 Backtesting Engine"):
        st.session_state.chat_mode = "backtesting"
        st.rerun()
    if st.button("🌌 3D Market Visualizer"):
        st.session_state.chat_mode = "market_visualizer"
        st.rerun()

    st.markdown("## Settings & Accessibility")
    if st.button("❓ Help / Quick Tour"):
        st.info("Help content goes here.")


# --- Main Content ---
if st.session_state.chat_mode == "welcome":
    st.markdown('<div class="welcome-card">', unsafe_allow_html=True)
    st.markdown("<h2>Welcome Assistant</h2>", unsafe_allow_html=True)
    st.markdown("<p>What can I help you with today?</p>", unsafe_allow_html=True)
    
    st.empty() # Spacer

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
            st.session_state.chat_mode = "screener" # Default insights view
            st.rerun()

    st.empty() # Spacer
    user_input = st.chat_input("Or, type a command...")
    if user_input:
        # Here you can re-integrate your handle_chat_command if needed
        st.info(f"Command received: {user_input}")

    st.markdown('</div>', unsafe_allow_html=True)

else:
    # --- Main Content Rendering based on chat_mode ---
    from app.views.routing import get_view
    view_func = get_view(st.session_state.get("chat_mode"))
    view_func(st, user_prefs)
