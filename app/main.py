import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import streamlit as st
from config.ticker_lists import TICKER_TO_NAME
import yfinance as yf
from backend.data_fetcher import get_ticker_data
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
import logging
import importlib


# --- CONFIGURATION (MUST BE AT THE TOP) ---
st.set_page_config(page_title="StockMatrix", layout="centered")

# --- Persistent User Preferences (Theme, Weights, Last Exchange/Ticker) ---
import json
PREFS_KEY = "stockmatrix_user_prefs"
def load_user_prefs():
    try:
        if PREFS_KEY in st.session_state:
            return st.session_state[PREFS_KEY]
        # Try to load from local storage (Streamlit query_params API)
        prefs = st.query_params.get(PREFS_KEY, [None])[0]
        if prefs:
            prefs = json.loads(prefs)
            st.session_state[PREFS_KEY] = prefs
            return prefs
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

import plotly.graph_objects as go

def initialize_session_state():
    """Initializes all required keys in the session state (our whiteboard)."""
    STATE_KEYS = {
        "ticker": "AAPL",
        "stock_data": None,
        "stock_info": None,
        "price_chart": None,
        "technicals": None,
        "fundamentals": None,
        "dcf": None,
        "piotroski": None,
        "beneish": None,
        "sentiment": None,
        "perception": None,
        "risk": None,
        "pdf_report": None,
    }
    for key, value in STATE_KEYS.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hi! Ask me to analyze a stock or compare stocks."}]

initialize_session_state()

def reset_analysis_data():
    """This is our 'eraser' for when the user types a new stock ticker."""
    st.session_state.stock_data = None
    st.session_state.stock_info = None
    st.session_state.price_chart = None
    st.session_state.technicals = None
    st.session_state.fundamentals = None
    st.session_state.dcf = None
    st.session_state.piotroski = None
    st.session_state.beneish = None
    st.session_state.sentiment = None
    st.session_state.perception = None
    st.session_state.risk = None
    st.session_state.pdf_report = None

# --- Backend & NLP Module Imports ---
from backend import (
    technical_analysis as ta_mod,
    fundamental_analysis as fa_mod,
    sentiment_analysis as sentiment_mod,
    news_risk_analyzer as news_mod,
    leaderboard_engine,
    screener_engine,
    report_generator,
    market_selector
)
from nlp.chat_router import handle_chat_command
from backend.report_generator import generate_pdf_report, generate_csv_report


from collections import OrderedDict


# --- Watchlist (Personalized) ---
watchlist = user_prefs.get("watchlist", [])
st.sidebar.markdown("---")
st.sidebar.markdown("### ⭐ Watchlist")
if watchlist:
    for ticker in watchlist:
        company_name = TICKER_TO_NAME.get(ticker.upper(), "Unknown Company")
        label = f"{ticker} - {company_name}"
        if st.sidebar.button(label, key=f"watchlist_{ticker}"):
            st.session_state["run_analysis_ticker"] = ticker
            st.session_state["chat_mode"] = "run_analysis"
            st.rerun()
else:
    st.sidebar.caption("No stocks in your watchlist yet.")

# Add/remove to watchlist UI
add_ticker = st.sidebar.text_input("Add Ticker to Watchlist", "", key="add_watchlist")
if st.sidebar.button("Add", key="add_watchlist_btn") and add_ticker:
    if add_ticker not in watchlist:
        watchlist.append(add_ticker.upper())
        user_prefs["watchlist"] = watchlist
        save_user_prefs(user_prefs)
        st.sidebar.success(f"Added {add_ticker.upper()} to watchlist!")
        st.rerun()
if watchlist:
    remove_options = ["-"] + [f"{t} - {TICKER_TO_NAME.get(t.upper(), 'Unknown Company')}" for t in watchlist]
    remove_selection = st.sidebar.selectbox("Remove from Watchlist", remove_options, key="remove_watchlist")
    if remove_selection != "-":
        # Extract ticker from selection (before the first ' - ')
        remove_ticker = remove_selection.split(" - ")[0]
        if st.sidebar.button("Remove", key="remove_watchlist_btn"):
            watchlist = [t for t in watchlist if t != remove_ticker]
            user_prefs["watchlist"] = watchlist
            save_user_prefs(user_prefs)
            st.rerun()


# --- Accessibility: High-Contrast Mode ---
contrast = user_prefs.get("contrast", False)
contrast_toggle = st.sidebar.checkbox("High Contrast Mode", value=contrast, key="contrast_toggle")
if contrast_toggle != contrast:
    user_prefs["contrast"] = contrast_toggle
    save_user_prefs(user_prefs)
    contrast = contrast_toggle


# --- System Theme Detection with User Override ---

# --- Force Dark Mode for All Users ---
theme = "dark"

# --- CSS for both themes, ensuring all text is visible ---

# --- Improved CSS for font visibility in all themes ---
css = '''
<style>
body, .stApp {
    background: #18191A !important;
    color: #F5F6FA !important;
}
.block-container, .stSidebar, .stSidebarContent, .stSidebarNav {
    background: #23272F !important;
    color: #F5F6FA !important;
}
.stSidebar, .stSidebarContent, .stSidebarNav, .sidebar-content, .sidebar-section {
    color: #FFD700 !important;
}
div[data-testid="stChatMessageGroup"] {
    background-color: #23272F !important;
    color: #F5F6FA !important;
}
.stExpander {
    background: #23272F !important;
    color: #F5F6FA !important;
}
.stButton > button, .stDownloadButton > button {
    background: linear-gradient(90deg, #FFD700 80%, #FFC300 100%) !important;
    color: #18191A !important;
    font-weight: bold !important;
}
.stTextInput > div > input, .stTextArea > div > textarea, .stSelectbox > div, .stSelectbox label, .stRadio label, .stCheckbox label {
    color: #F5F6FA !important;
    background: #23272F !important;
    font-weight: 500 !important;
}
.stMarkdown, .stText, .stExpander, .stDataFrame, .stRadio, .stSelectbox, .stButton, .stSlider, .stDownloadButton, .stChatInputContainer, .stChatMessage, .stChatInput, .stTextInput, .stTextArea, .stExpanderHeader, .stExpanderContent, .stAlert, .stSubheader, .stHeader, .stCaption, .stTable, .stDataFrame {
    color: #F5F6FA !important;
}
h1, h2, h3, h4, h5, h6, .stSubheader, .stHeader {
    color: #FFD700 !important;
    font-weight: 900 !important;
    letter-spacing: 1px;
}
/* Dropdown selector styling */
.stSelectbox > div {
    background: linear-gradient(90deg, #FFD700, #FFC300) !important;
    color: #18191A !important;
    font-weight: bold !important;
    border-radius: 8px !important;
}

/* Selected option text */
.stSelectbox div[data-baseweb="select"] > div {
    color: #18191A !important;
    background-color: transparent !important;
}
</style>
'''

# High-contrast mode CSS
if contrast:
    css += '''
    <style>
    body, .stApp, .block-container, .stExpander, div[data-testid="stChatMessageGroup"] {
        background: #000 !important;
        color: #FFD700 !important;
    }
    .stButton > button, .stDownloadButton > button {
        background: #FFD700 !important;
        color: #000 !important;
        border: 2px solid #FFD700 !important;
    }
    .stMarkdown, .stText, .stExpander, .stDataFrame, .stRadio, .stSelectbox, .stButton, .stSlider, .stDownloadButton, .stChatInputContainer, .stChatMessage, .stChatInput, .stTextInput, .stTextArea, .stSelectbox > div, .stSelectbox label, .stRadio label, .stExpanderHeader, .stExpanderContent, .stAlert, .stSubheader, .stHeader, .stCaption, .stTable, .stDataFrame, .stCheckbox label {
        color: #FFD700 !important;
    }
    </style>
    '''


# --- Improved Top Banner: Always visible and styled for theme ---
banner_color = "#FFD700"
text_color = "#18191A"
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@900&display=swap" rel="stylesheet">
<style>
.top-banner-title {
    font-family: 'Poppins', sans-serif !important;
    font-size: 3.2rem !important;
    font-weight: 900 !important;
    letter-spacing: 2px;
    color: #18191A !important;
    vertical-align: middle;
    display: inline-block;
}
</style>
<div class="top-banner" style="width:100%;padding:24px 0 16px 0;text-align:center;background:#FFD700;border-radius:0 0 18px 18px;box-shadow:0 4px 32px rgba(10,31,68,0.10);">
    <span class="top-banner-title" style="background: #FFD700; padding: 0 16px; border-radius: 12px; color: #18191A !important;">🪙 StockMatrix</span>
</div>
""", unsafe_allow_html=True)
st.markdown('<meta name="viewport" content="width=device-width, initial-scale=1">', unsafe_allow_html=True)
st.markdown(css, unsafe_allow_html=True)

st.markdown("""
<div class='curated-footer' style='color: #FFFFFF; text-align: right;'>Curated and powered by Kushagra Bansal</div>
""", unsafe_allow_html=True)



# ...existing code...
st.set_option('client.showErrorDetails', True)
# =============================================================================
# --- Cached Helper Functions ---
@st.cache_data(ttl=3600)
def get_technical_analysis(ticker, basis: str = "annual"):
    return ta_mod.analyze_technical_indicators(ticker, basis=basis.lower())

@st.cache_data(ttl=3600)
def get_fundamental_analysis(ticker, basis: str = "annual"):
    return fa_mod.analyze_fundamentals(ticker, basis=basis.lower())

@st.cache_data(ttl=1800)
def get_perception_analysis(ticker):
    # This now calls your new function from the sentiment_analysis.py file
    return sentiment_mod.analyze_perception(ticker)

@st.cache_data(ttl=1800)
def get_news_risk_analysis(ticker, basis: str = "annual"):
    return news_mod.fetch_news_risk(ticker, basis=basis.lower())

# Increase cache times and add hash_funcs for yfinance objects

# Use centralized fetcher for info
@st.cache_data(ttl=86400)
def get_yf_info(ticker):
    return get_ticker_data(ticker).get("info", {})


# Use centralized fetcher for history (always fetches full history, slice in-memory)
@st.cache_data(ttl=86400)
def get_stock_history(ticker, period="6mo"):
    import pandas as pd
    history = get_ticker_data(ticker).get("history", {})
    if not history or "Close" not in history:
        return pd.DataFrame()
    df = pd.DataFrame(history)
    # Slice by period if possible (default: last 6 months)
    if period == "6mo":
        if not df.empty and hasattr(df.index, 'max'):
            cutoff = pd.Timestamp.now() - pd.DateOffset(months=6)
            df = df[df.index >= cutoff]
    return df

@st.cache_data(ttl=86400) # Cache for one day (86400 seconds)
def cached_get_risk_free_rate():
    """
    This is a Streamlit-aware function in main.py.
    It calls the backend function and caches the result.
    """
    # CORRECT: Calls the 'get_risk_free_rate' function from the 'fa_mod' module
    return fa_mod.get_risk_free_rate()

# =============================================================================
# --- DISPLAY HELPER FUNCTIONS ---
# =============================================================================


# ... (The rest of your main.py file, like session state initialization, etc.)
# --- Load Static Imports ---
from backend.market_selector import get_top_50_tickers
from nlp.chat_router import handle_chat_command
from backend.screener_engine import calculate_volatility

# --- Streamlit Config ---

# --- Session State Initialization ---
DEFAULT_STATE = {
    "chat_history": [],
    "greeted": False,
    "chat_mode": None,
    "show_insight_buttons": False,
    "essential_data": {
        "exchanges": ["NSE", "NYSE", "LSE", "HKEX", "TSE"],
        "basic_tickers": ["AAPL", "MSFT", "GOOG"]
    }
}

for key, value in DEFAULT_STATE.items():
    st.session_state.setdefault(key, value)


# --- Onboarding Modal for First-Time Users ---
if not user_prefs.get("onboarded", False):
    with st.sidebar.expander("👋 Welcome! Start Here", expanded=True):
        st.markdown("""
        # Welcome to StockMatrix!
        - Analyze top stocks across global exchanges
        - Run analysis, generate reports, and get insights
        - Use the sidebar to switch theme and access your preferences
        - Click the help button below for a quick tour anytime
        """)
        if st.button("Got it! Hide this panel", key="onboard_btn"):
            user_prefs["onboarded"] = True
            save_user_prefs(user_prefs)



# --- Help Button for Interactive Tips ---
if st.sidebar.button("❓ Help / Quick Tour"):
    st.info("""
    **Quick Tips:**
    - Use the sidebar to change theme and access onboarding again.
    - Type `RA` for Run Analysis, `GR` for Generate Report, `IG` for Insights.
    - Customize scoring models and download reports.
    - Add stocks to your watchlist for quick access.
    - Use the leaderboard and screener for discovery.
    """)

# --- Strategic Insights Tab Button ---
if st.sidebar.button("📈 Strategic Insights"):
    st.session_state["chat_mode"] = "strategic_insights"
    st.rerun()


# --- Export/Share Insights ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 📤 Export/Share Insights")
if st.session_state.get("final_score") is not None:
    ticker = st.session_state.get('run_analysis_ticker', '')
    company_name = TICKER_TO_NAME.get(ticker.upper(), "Unknown Company")
    summary = f"Stock: {ticker} - {company_name}\nScore: {st.session_state['final_score']}\nVerdict: {st.session_state['final_verdict']}"
    st.sidebar.download_button("Download Summary", summary, file_name="stockmatrix_summary.txt")
    st.sidebar.code(summary, language="text")
    st.sidebar.caption("Copy and share this summary anywhere!")

# --- Initial Chat Message ---
if not st.session_state.greeted:
    greeting_msg = ("""
        👋 **Welcome to StockMatrix** — your AI-powered stock research assistant.

        I analyze the top 50 stocks across major global exchanges:  
        🇮🇳 NSE, 🇺🇸 NYSE, 🇬🇧 LSE, 🇭🇰 HKEX, and 🇯🇵 TSE.

        What would you like to do today?

        - 📊 **Run Analysis**  
        - 🧾 **Generate a Report**  
        - 💡 **Get Insights**

        Type your choice below to begin:
        """)
    
    st.session_state.chat_history.append({"role": "user", "content": greeting_msg})
    st.session_state.greeted = True

for msg in st.session_state.chat_history:
    st.chat_message(msg["role"]).markdown(msg["content"])

with st.expander("💡 Quick Tips", expanded=False):
    st.markdown("""
    **You can type:**
    - `RA` or `Run Analysis` to analyze a stock
    - `GR` or `Generate Report` to get a downloadable PDF/CSV
    - `IG` or `Insight Generation` for screener and leaderboard
        - `Screener` to find high-potential stocks
        - `Leaderboard` to view top-ranked stocks
    """)

user_input = st.chat_input("How can I help you today?", key="main_user_input")

# --- Command Processing ---
# --- Command Processing ---
if user_input:
    st.session_state.show_insight_buttons = False
    
    # Initialize all variables with default values
    response = None
    screener_data = None

    # Handle special commands
    if user_input.lower() == "screener":
        st.session_state.chat_mode = "screener"
        st.rerun()
    elif user_input.lower() == "leaderboard":
        st.session_state.chat_mode = "stock_leaderboard"
        st.rerun()

    st.session_state.chat_history.append({"role": "user", "content": user_input})
    cmd = user_input.lower().strip().replace(" ", "")

    # Process commands
    if cmd in ["ra", "runanalysis"]:
        st.session_state.chat_mode = "run_analysis"
        response = "You selected Run Analysis. Please proceed."
    elif cmd in ["gr", "generatereport", "report"]:
        st.session_state.chat_mode = "report"
        response = "You selected Report Generator. Please proceed."
    elif cmd in ["ig", "insight", "insightgeneration"]:
        st.session_state.chat_mode = "insight_generation"
        response = "You selected **Insight Generation**. Please choose an option:"
        st.session_state.show_insight_buttons = True
        st.rerun()
    else:
        response, screener_data = handle_chat_command(user_input)
        if "chat_mode" not in st.session_state:
            st.session_state.chat_mode = None

    # Safe response handling
    if response:
        # Only show if we're not in a specific mode
        if st.session_state.get("chat_mode") in [None, ""]:
            st.chat_message("assistant").markdown(response)
        # For specific modes, let their sections handle the display


    # Handle screener data if present and valid
    import pandas as pd
    if screener_data is not None:
        if isinstance(screener_data, pd.DataFrame):
            try:
                st.dataframe(screener_data)
            except Exception:
                st.warning("Could not display screener data as a table.")
        elif isinstance(screener_data, list) and screener_data and isinstance(screener_data[0], dict):
            try:
                st.dataframe(pd.DataFrame(screener_data))
            except Exception:
                st.warning("Could not display screener data as a table.")
        else:
            st.info(str(screener_data))

    # Handle invalid commands
    if (not response and 
        st.session_state.get("chat_mode") in [None, ""]):
        st.chat_message("assistant").markdown(
            "⚠️ Sorry, I can only help with:\n\n"
            "- Run Analysis (RA)\n"
            "- Generate Report (GR)\n"
            "- Insight Generation (IG)\n\n"
            "Please type one of these to continue."
        )

# --- Show Insight Options if Flag is Set (for IG command) ---
if st.session_state.get("chat_mode") == "insight_generation":
    st.markdown("**Choose an Insight Option:**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Stock Screener", key="insight_screener_btn"):
            st.session_state.chat_mode = "screener"
            st.session_state.show_insight_buttons = False
            st.rerun()
    with col2:
        if st.button("Stock Leaderboard", key="insight_leaderboard_btn"):
            st.session_state.chat_mode = "stock_leaderboard"
            st.session_state.show_insight_buttons = False
            st.rerun()
    # Optionally add more insight options here
    # Reset flag after showing
    st.session_state.show_insight_buttons = False
# --- Main Content Rendering -
from app.views.routing import get_view
view_func = get_view(st.session_state.get("chat_mode"))
view_func(st, user_prefs)