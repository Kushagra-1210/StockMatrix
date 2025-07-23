
# main.py
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import streamlit as st
import yfinance as yf
from backend.data_fetcher import get_ticker_data
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
import logging
import importlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# =============================================================================

# --- CONFIGURATION (MUST BE AT THE TOP) ---
# =============================================================================
st.set_page_config(page_title="StockMatrix", layout="centered")

# --- Persistent User Preferences (Theme, Weights, Last Exchange/Ticker) ---
import json
PREFS_KEY = "stockmatrix_user_prefs"
def load_user_prefs():
    try:
        if PREFS_KEY in st.session_state:
            return st.session_state[PREFS_KEY]
        # Try to load from local storage (Streamlit experimental API)
        prefs = st.experimental_get_query_params().get(PREFS_KEY, [None])[0]
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
        if st.sidebar.button(f"{ticker}", key=f"watchlist_{ticker}"):
            st.session_state["run_analysis_ticker"] = ticker
            st.session_state["chat_mode"] = "run_analysis"
            st.experimental_rerun()
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
        st.experimental_rerun()
if watchlist:
    remove_ticker = st.sidebar.selectbox("Remove from Watchlist", ["-"] + watchlist, key="remove_watchlist")
    if remove_ticker != "-" and st.sidebar.button("Remove", key="remove_watchlist_btn"):
        watchlist = [t for t in watchlist if t != remove_ticker]
        user_prefs["watchlist"] = watchlist
        save_user_prefs(user_prefs)
        st.experimental_rerun()


# --- Accessibility: High-Contrast Mode ---
contrast = user_prefs.get("contrast", False)
contrast_toggle = st.sidebar.checkbox("High Contrast Mode", value=contrast, key="contrast_toggle")
if contrast_toggle != contrast:
    user_prefs["contrast"] = contrast_toggle
    save_user_prefs(user_prefs)
    contrast = contrast_toggle


# --- System Theme Detection with User Override ---
import streamlit.components.v1 as components
import streamlit as st
import json

def get_system_theme():
    # Use a hidden component to get system theme via JS
    theme = st.session_state.get("system_theme", None)
    if theme is not None:
        return theme
    # Inject JS to detect system theme and send to Streamlit
    components.html('''
        <script>
        const theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        window.parent.postMessage({isDark: theme === 'dark'}, '*');
        window.addEventListener('message', (event) => {
            if (event.data && event.data.setTheme) {
                window.parent.postMessage({isDark: event.data.setTheme === 'dark'}, '*');
            }
        });
        </script>
    ''', height=0)
    # Fallback to light if not set
    return "light"

# Listen for theme from frontend (Streamlit custom component workaround)
if "system_theme" not in st.session_state:
    st.session_state["system_theme"] = get_system_theme()

# User preference: if not set, use system theme
theme = user_prefs.get("theme", None)
if theme is None:
    theme = st.session_state.get("system_theme", "light")

# Sidebar theme selector (always available)
theme_toggle = st.sidebar.selectbox(
    "Theme",
    ["System Default", "light", "dark"],
    index=0 if user_prefs.get("theme", None) is None else (1 if theme=="light" else 2)
)
if theme_toggle == "System Default":
    # Remove user override, use system
    if "theme" in user_prefs:
        user_prefs.pop("theme")
        save_user_prefs(user_prefs)
    theme = st.session_state.get("system_theme", "light")
else:
    new_theme = "light" if theme_toggle == "light" else "dark"
    if user_prefs.get("theme", None) != new_theme:
        user_prefs["theme"] = new_theme
        save_user_prefs(user_prefs)
    theme = new_theme

# --- CSS for both themes, ensuring all text is visible ---

# --- Improved CSS for font visibility in all themes ---
css = ""
if theme == "dark":
    css += '''
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
    </style>
    '''
else:
    css += '''
    <style>
    body {
        background: #F8F9FB !important;
        min-height: 100vh;
        color: #18191A !important;
    }
    .stApp {
        background: #F8F9FB !important;
        min-height: 100vh;
        color: #18191A !important;
    }
    .block-container {
        background: #fff !important;
        color: #18191A !important;
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 4px 32px rgba(10, 31, 68, 0.10);
    }
    .stSidebar, .stSidebarContent, .stSidebarNav, .sidebar-content, .sidebar-section {
        background: #f5f6fa !important;
        color: #FFD700 !important;
        border-right: 1.5px solid #e0e0e0 !important;
        box-shadow: 2px 0 16px rgba(10, 31, 68, 0.06);
        border-top-right-radius: 18px;
        border-bottom-right-radius: 18px;
    }
    div[data-testid="stChatMessageGroup"] {
        background-color: #F5F5F5  !important;
        padding: 16px !important;
        border-radius: 12px !important;
        color: #18191A !important;
    }
    .stExpander {
        background: #F8F9FB !important;
        color: #18191A !important;
    }
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(90deg, #FFD700 80%, #FFC300 100%) !important;
        color: #18191A !important;
        font-weight: bold !important;
    }
    .stTextInput > div > input, .stTextArea > div > textarea, .stSelectbox > div, .stSelectbox label, .stRadio label, .stCheckbox label {
        color: #18191A !important;
        background: #FFFFFF !important;
        font-weight: 500 !important;
    }
    .stMarkdown, .stText, .stExpander, .stDataFrame, .stRadio, .stSelectbox, .stButton, .stSlider, .stDownloadButton, .stChatInputContainer, .stChatMessage, .stChatInput, .stTextInput, .stTextArea, .stExpanderHeader, .stExpanderContent, .stAlert, .stSubheader, .stHeader, .stCaption, .stTable, .stDataFrame {
        color: #18191A !important;
    }
    h1, h2, h3, h4, h5, h6, .stSubheader, .stHeader {
        color: #FFD700 !important;
        font-weight: 900 !important;
        letter-spacing: 1px;
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
if theme == "dark" or contrast:
    banner_color = "#FFD700"
    text_color = "#18191A"
else:
    banner_color = "#fff"
    text_color = "#18191A"
st.markdown(f"""
    <div class="top-banner" style="width:100%;padding:18px 0 10px 0;text-align:center;background:{banner_color};border-radius:0 0 18px 18px;box-shadow:0 4px 32px rgba(10,31,68,0.10);">
        <span style='font-size:2.2rem;font-weight:900;letter-spacing:2px;color:{text_color};vertical-align:middle;'>🪙 StockMatrix</span>
    </div>
    """, unsafe_allow_html=True)
st.markdown('<meta name="viewport" content="width=device-width, initial-scale=1">', unsafe_allow_html=True)
st.markdown(css, unsafe_allow_html=True)

st.markdown("<div class='curated-footer' style='color: #000000;'>Curated and powered by Kushagra Bansal</div>", unsafe_allow_html=True)



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


# =============================================================================
# --- MAIN APP LOGIC STARTS HERE ---
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

# --- Export/Share Insights ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 📤 Export/Share Insights")
if st.session_state.get("final_score") is not None:
    summary = f"Stock: {st.session_state.get('run_analysis_ticker', '')}\nScore: {st.session_state['final_score']}\nVerdict: {st.session_state['final_verdict']}"
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
    context = None  # Explicitly initialize context

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
        response, screener_data, context = handle_chat_command(user_input)
        if "chat_mode" not in st.session_state:
            st.session_state.chat_mode = None

    # Safe response handling
    if response:
        # Only show if we're not in a specific mode
        if st.session_state.get("chat_mode") in [None, ""]:
            st.chat_message("assistant").markdown(response)
        # For specific modes, let their sections handle the display
    
    # Handle screener data if present
    if screener_data:
        st.dataframe(screener_data)

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

# --- Main Content Rendering ---

if st.session_state.get("chat_mode") == "screener":
    if st.button("← Back to Main Menu"):
        st.session_state.chat_mode = None
        st.rerun()
    st.subheader("📊 Screener Engine")
    basis = st.radio("Select Analysis Period", ["Quarterly", "Annual"], horizontal=True, key="screener_basis")
    st.markdown("**Choose an exchange**")
    exchange = st.selectbox("", ["NSE", "HKEX", "NYSE", "LSE", "TSE"], key="screener_exchange")
    col1, col2, col3 = st.columns(3)
    with col1:
        min_upside = col1.slider("Minimum DCF Upside (%)", -50, 200, 20)
    with col2:
        min_ta = st.slider("Minimum TA Score", 0, 100, 50)
    with col3:
        max_vol = st.slider("Volatility Threshold (Annualized %)", 0, 100, 50)

    # --- Real-time auto-refresh toggle ---
    auto_refresh = user_prefs.get("screener_auto_refresh", False)
    auto_refresh_toggle = st.checkbox("🔄 Auto-refresh every 30 seconds", value=auto_refresh, key="screener_auto_refresh")
    if auto_refresh_toggle != auto_refresh:
        user_prefs["screener_auto_refresh"] = auto_refresh_toggle
        save_user_prefs(user_prefs)
        auto_refresh = auto_refresh_toggle

    if st.button("🔍 Find Stocks", key="screener_button") or auto_refresh:
        tickers = get_top_50_tickers(exchange)
        with st.spinner(f"Screening stocks on {exchange}..."):
            results = screener_engine.screen_stocks(
                tickers=tickers,
                min_upside=min_upside,
                min_ta=min_ta,
                max_volatility=max_vol
            )
            st.session_state.screener_results = results
        if auto_refresh:
            import time
            time.sleep(30)
            st.experimental_rerun()
    else:
        results = st.session_state.get("screener_results", [])

    if results:
        st.markdown(f"#### ✅ {len(results)} stocks matched your criteria.")
        df = pd.DataFrame(results)
        def highlight_cells(row):
            styles = ['' for _ in row]
            try:
                upside_val = float(str(row['Upside (%)']).replace('%', ''))
                if upside_val >= 50:
                    styles[1] = 'background-color: #d4edda; color: #155724;'
                elif upside_val >= 20:
                    styles[1] = 'background-color: #fff3cd; color: #856404;'
            except (ValueError, TypeError):
                pass
            try:
                ta_score = row['TA Score']
                if ta_score >= 70:
                    styles[2] = 'background-color: #d4edda; color: #155724;'
            except (ValueError, TypeError):
                pass
            try:
                vol_val = row['Volatility (%)']
                if vol_val > 75:
                    styles[3] = 'background-color: #f8d7da; color: #721c24;'
            except (ValueError, TypeError):
                pass
            return styles
        styled_df = df.style.apply(highlight_cells, axis=1).format({
            "Upside (%)": "{:.2f}%",
            "TA Score": "{:.2f}",
            "Volatility (%)": "{:.2f}%"
        })
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            height=min(len(df) * 40 + 40, 600)
        )

# =============================================================================
# START OF REPLACEMENT BLOCK: STOCK LEADERBOARD
# =============================================================================
elif st.session_state.get("chat_mode") == "stock_leaderboard":
    if st.button("← Back to Main Menu"):
        st.session_state.chat_mode = None
        st.rerun()

    st.subheader("🏆 Stock Leaderboard")

    # --- CONTROLS SECTION FOR THE LEADERBOARD ---
    with st.expander("🎛️ Customize Leaderboard Scoring Model"):
        st.markdown("Adjust the weights for each analysis category. **They must add up to 100%.**")

        if 'user_weights' not in st.session_state:
            st.session_state.user_weights = {"fa": 35, "ta": 35, "sentiment": 20, "news": 10}

        weights = st.session_state.user_weights
        # Use unique keys for leaderboard sliders to prevent conflicts with other pages
        weights["fa"] = st.slider("Fundamental Analysis (%)", 0, 100, weights["fa"], key="leaderboard_fa_slider")
        weights["ta"] = st.slider("Technical Analysis (%)", 0, 100, weights["ta"], key="leaderboard_ta_slider")
        weights["sentiment"] = st.slider("Strategic Perception Analysis (%)", 0, 100, weights["sentiment"], key="leaderboard_sentiment_slider")
        weights["news"] = st.slider("News & Risk Analysis (%)", 0, 100, weights["news"], key="leaderboard_news_slider")

    st.markdown("---")

    basis = st.radio("Select Analysis Period", ["Quarterly", "Annual"], horizontal=True, key="leaderboard_basis")
    exchange = st.selectbox("Select Stock Exchange", ["NSE", "NYSE", "TSE", "LSE", "HKEX"], key="leaderboard_exchange")

    # --- STANDARDIZED AND ROBUST BUTTON LOGIC ---
    total_weight_leaderboard = sum(st.session_state.user_weights.values())
    is_leaderboard_disabled = (total_weight_leaderboard != 100)

    # In main.py, under the "stock_leaderboard" section

    if st.button("🔄 Compute/Refresh Data", disabled=is_leaderboard_disabled):
        with st.spinner(f"Computing leaderboard for {exchange}..."):
            # Call the backend function that does all the work
            df = leaderboard_engine.get_leaderboard(exchange) # Fetch all data
            if df is not None and not df.empty:
                st.session_state.leaderboard_df = df
            else:
                st.session_state.leaderboard_df = None # Clear old data on error
                st.success("Leaderboard data refreshed successfully!")
    if 'leaderboard_df' in st.session_state and st.session_state.leaderboard_df is not None:
        st.markdown("###  Leaderboard Results")
        df = st.session_state.leaderboard_df.copy()
    # ...existing code...
        # Map weights to columns, ensuring only News-related columns (not Safety Score) are shown
        col_map = {
            "fa": ["FA Score", "Fundamental Score"],
            "ta": ["TA Score", "Technical Score"],
            "sentiment": ["Perception Score", "Strategic Perception Score", "Sentiment Score"],
            # Only allow News Score or Risk Score, never Safety Score
            "news": ["News Score", "Risk Score", "risk_score", "news_score"]
        }
        def find_col(possibles):
            # Try exact match first
            for c in possibles:
                if c in df.columns:
                    return c
            # Try lowercase match for robustness
            lower_cols = {col.lower(): col for col in df.columns}
            for c in possibles:
                if c.lower() in lower_cols:
                    return lower_cols[c.lower()]
            return None
        fa_col = find_col(col_map["fa"])
        ta_col = find_col(col_map["ta"])
        sp_col = find_col(col_map["sentiment"])
        news_col = find_col(col_map["news"])
        final_col = None
        for c in ["Final Score", "Combined Score", "Score"]:
            if c in df.columns:
                final_col = c
                break
        # Build columns to show in order
        show_cols = ["Ticker"]
        if weights.get("fa", 0) > 0 and fa_col:
            show_cols.append(fa_col)
        if weights.get("ta", 0) > 0 and ta_col:
            show_cols.append(ta_col)
        if weights.get("sentiment", 0) > 0 and sp_col:
            show_cols.append(sp_col)
        if weights.get("news", 0) > 0:
            if news_col:
                show_cols.append(news_col)
            else:
                st.warning("News score column is missing in the leaderboard data. Please check if the backend is returning a News or Risk Score column.")
        if final_col:
            show_cols.append(final_col)
        # Remove any 'Safety Score' column if present
        if "Safety Score" in show_cols:
            show_cols.remove("Safety Score")
        st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
# =============================================================================
# END OF REPLACEMENT BLOCK
# =============================================================================

elif st.session_state.get("chat_mode") == "insight_generation":
    if st.session_state.show_insight_buttons:
        st.subheader("🔍 Insight Generation ")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Screener Engine"):
                st.session_state.chat_mode = "screener"
                st.session_state.show_insight_buttons = False
                st.rerun()
                
        with col2:
            if st.button("📈 Stock Leaderboard"):
                st.session_state.chat_mode = "stock_leaderboard"
                st.session_state.show_insight_buttons = False
                st.rerun()

# =============================================================================
# START OF REPLACEMENT BLOCK 1: RUN ANALYSIS
# =============================================================================
elif st.session_state.get("chat_mode") == "run_analysis":
    st.subheader("⚙️ Run Analysis Module")

    st.markdown('<div class="ra-selectbox-wrapper">', unsafe_allow_html=True)
    st.markdown("Select Data Basis")
    basis = st.radio(label="", options=["Quarterly", "Annual"], horizontal=True, key="run_analysis_basis")

    st.markdown("1. Choose an Exchange")
    exchange = st.selectbox("", ["NSE", "HKEX", "NYSE", "LSE", "TSE"], key="run_analysis_exchange")

    tickers = get_top_50_tickers(exchange)

    if "last_exchange" not in st.session_state or st.session_state.last_exchange != exchange:
        st.session_state["run_analysis_ticker"] = tickers[0] if tickers else None
        st.session_state.last_exchange = exchange

    st.markdown("2. Choose a Stock", unsafe_allow_html=True)
    selected_ticker = st.selectbox("", tickers, key="run_analysis_ticker")
    st.markdown('</div>', unsafe_allow_html=True)


    st.markdown("---")
    # --- UX FIX: Keep expander open when sliders are changed ---
    if 'analysis_expander_open' not in st.session_state:
        st.session_state.analysis_expander_open = True

    def open_expander():
        st.session_state.analysis_expander_open = True

    def close_expander():
        st.session_state.analysis_expander_open = False

    # Use the expander with expanded state from session
    with st.expander("🎛️ Customize Scoring Model", expanded=st.session_state.analysis_expander_open):
        st.markdown("Adjust the weights for each analysis category. **They must add up to 100%.**")

        if 'user_weights' not in st.session_state:
            st.session_state.user_weights = {"fa": 35, "ta": 35, "sentiment": 20, "news": 10}

        weights = st.session_state.user_weights
        weights["fa"] = st.slider("Fundamental Analysis (%)", 0, 100, weights["fa"], key="analysis_fa_slider", on_change=open_expander)
        weights["ta"] = st.slider("Technical Analysis (%)", 0, 100, weights["ta"], key="analysis_ta_slider", on_change=open_expander)
        weights["sentiment"] = st.slider("Strategic Perception Analysis (%)", 0, 100, weights["sentiment"], key="analysis_sentiment_slider", on_change=open_expander)
        weights["news"] = st.slider("News & Risk Analysis (%)", 0, 100, weights["news"], key="analysis_news_slider", on_change=open_expander)

        # Add a button to allow user to close the expander if they want
        st.button("Close Customization Panel", on_click=close_expander)

    st.markdown("---")


    col1, col2 = st.columns(2)
    with col1:
        auto_refresh = st.checkbox("🔄 Auto-refresh every 30 seconds", key="auto_refresh_checkbox")



        if st.button("Stock Price", key="run_analysis_price_btn") or (st.session_state.get("auto_refresh_checkbox") and st.session_state.get("auto_refreshing")):
            st.session_state.auto_refreshing = auto_refresh
            try:
                # Use centralized data fetcher
                ticker_data = get_ticker_data(selected_ticker)
                info = ticker_data.get("info", {})
                history = ticker_data.get("history", {})
                current_price = info.get("currentPrice", "N/A")
                currency = info.get("currency", "")
                market_cap = info.get("marketCap", "N/A")
                volume = info.get("volume", "N/A")

                st.subheader(f"{info.get('shortName', selected_ticker)} ({selected_ticker})")
                st.markdown(f"""
                - **Current Price**: {current_price} {currency}
                - **Market Cap**: {market_cap:,}
                - **Volume**: {volume:,}
                - **As of**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """)

                # --- Enhanced Chart Options ---
                chart_type = st.selectbox(
                    "Select Chart Type",
                    ["Line", "Candlestick", "Bar"],
                    key="run_analysis_chart_type"
                )
                show_moving_avg = st.checkbox("Show Moving Average (20d)", value=False, key="run_analysis_ma")
                show_volume = st.checkbox("Show Volume", value=False, key="run_analysis_vol")

                if history and "Close" in history:
                    import pandas as pd
                    close_series = pd.Series(history["Close"])
                    df = pd.DataFrame({"Close": close_series})
                    if "Open" in history and "High" in history and "Low" in history:
                        df["Open"] = pd.Series(history["Open"])
                        df["High"] = pd.Series(history["High"])
                        df["Low"] = pd.Series(history["Low"])
                    if "Volume" in history:
                        df["Volume"] = pd.Series(history["Volume"])

                    import plotly.graph_objs as go
                    fig = go.Figure()
                    if chart_type == "Line":
                        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Close Price"))
                    elif chart_type == "Candlestick" and all(col in df for col in ["Open", "High", "Low", "Close"]):
                        fig.add_trace(go.Candlestick(
                            x=df.index,
                            open=df["Open"],
                            high=df["High"],
                            low=df["Low"],
                            close=df["Close"],
                            name="Candlestick"
                        ))
                    elif chart_type == "Bar":
                        fig.add_trace(go.Bar(x=df.index, y=df["Close"], name="Close Price"))

                    # Moving Average
                    if show_moving_avg:
                        df["MA20"] = df["Close"].rolling(window=20).mean()
                        fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA 20d", line=dict(dash="dash")))

                    # Volume
                    if show_volume and "Volume" in df:
                        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume", yaxis="y2", marker_color="rgba(0,0,255,0.2)"))
                        fig.update_layout(
                            yaxis2=dict(overlaying="y", side="right", title="Volume", showgrid=False),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )

                    fig.update_layout(
                        title="Price Trend (6 Months)",
                        xaxis_title="Date",
                        yaxis_title=f"Price ({currency})",
                        template="plotly_white"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No price history available.")

                if auto_refresh:
                    components.html(
                        """
                        <meta http-equiv=\"refresh\" content=\"30\">
                        """,
                        height=0,
                    )
            except Exception as e:
                st.error(f"Error fetching stock data: {str(e)}")

    with col2:
        total_weight = sum(st.session_state.user_weights.values())
        is_disabled = (total_weight != 100)

        if st.button("Run Analysis", key="run_analysis_btn", disabled=is_disabled):
            reset_analysis_data()
            with st.spinner(f"🔍 Running {basis.lower()} analysis for {selected_ticker}..."):
                try:
                    # --- ACTION: Fetch data and SAVE to the whiteboard ---
                    st.session_state.technicals = get_technical_analysis(selected_ticker, basis=basis.lower())
                    st.session_state.fundamentals = get_fundamental_analysis(selected_ticker, basis=basis.lower())
                    st.session_state.perception = get_perception_analysis(selected_ticker)
                    st.session_state.risk = get_news_risk_analysis(selected_ticker, basis=basis.lower())

                    # Also store the final score and verdict in the whiteboard
                    if "error" not in st.session_state.fundamentals and "error" not in st.session_state.technicals:
                        user_weights = st.session_state.user_weights
                        final_score = round(
                            (user_weights["fa"] / 100) * st.session_state.fundamentals.get("Fundamental Score", 0) +
                            (user_weights["ta"] / 100) * st.session_state.technicals.get("ta_score", 0) +
                            (user_weights["sentiment"] / 100) * st.session_state.perception.get("score", 0) * 10 +
                            (user_weights["news"] / 100) * st.session_state.risk.get("risk_score", 50), 2
                        )
                        final_verdict = ("Strong Buy" if final_score >= 80 else "Buy" if final_score >= 65 else "Hold" if final_score >= 50 else "Sell")

                        st.session_state.final_score = final_score
                        st.session_state.final_verdict = final_verdict
                        st.session_state.final_weights = user_weights

                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
        st.divider()

        # --- DISPLAY LOGIC: This section reads from the whiteboard (st.session_state) ---


        weights = st.session_state.user_weights


        # Only show Technical Analysis if its weight is not zero
        if st.session_state.technicals and weights.get("ta", 0) > 0:
            with st.expander("🧪 Technical Analysis", expanded=True):
                data = st.session_state.technicals
                if "error" in data:
                    st.error(f"Analysis Failed: {data['error']}")
                else:
                    st.metric(label="Technical Score", value=f"{data.get('ta_score', 0)}/100")
                    st.write(f"**Verdict:** `{data.get('verdict', 'N/A')}`")

                    # --- TECHNICAL INDICATOR BREAKDOWN ---
                    indicators = data.get('indicators', {})
                    if indicators:
                        st.markdown("---")
                        st.markdown("#### Key Technical Indicators:")
                        # Show as columns if there are a few, else as a table
                        if isinstance(indicators, dict):
                            keys = list(indicators.keys())
                            n = len(keys)
                            if n > 0:
                                cols = st.columns(min(n, 4))
                                for i, k in enumerate(keys):
                                    with cols[i % 4]:
                                        st.metric(k, indicators[k])
                        else:
                            st.write(indicators)
                    # Optionally show any notes
                    notes = data.get('notes', [])
                    if notes:
                        st.markdown("**Technical Analysis Notes:**")
                        for note in notes:
                            st.caption(f"📝 {note}")


        # Only show Fundamental Analysis if its weight is not zero
        if st.session_state.fundamentals and weights.get("fa", 0) > 0:
            with st.expander("📊 Fundamental Analysis", expanded=True):
                data = st.session_state.fundamentals

                # --- NEW DISPLAY LOGIC FOR THE 3-FACTOR MODEL ---

                # 1. Display the Final Score and Verdict
                final_score = data.get("Fundamental Score")
                verdict = data.get("Verdict")
                if final_score is not None:
                    st.metric(label="Combined Fundamental Score", value=f"{final_score:.2f}/100")
                    st.subheader(f"Verdict: {verdict}")
                st.markdown("---")

                # 2. Display the Breakdown of Sub-Scores
                st.markdown("#### Score Breakdown:")
                breakdown = data.get("Breakdown", {})

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Piotroski F-Score", breakdown.get('Piotroski F-Score', "N/A"))
                with col2:
                    st.metric("Altman Z-Score", breakdown.get('Altman Z-Score', "N/A"))
                    st.caption(f"Risk: {breakdown.get('Bankruptcy Risk', 'N/A')}")
                with col3:
                    st.metric("Beneish M-Score", breakdown.get('Beneish M-Score', "N/A"))
                    st.caption(f"Risk: {breakdown.get('Manipulation Risk', 'N/A')}")

                st.markdown("---")

                # 3. Display Any Notes or Warnings
                notes = data.get("Notes", [])
                if notes:
                    st.markdown("#### Analysis Notes:")
                    for note in notes:
                        st.caption(f"📝 {note}")

        # Only show Strategic Perception Analysis if its weight is not zero
        if st.session_state.perception and weights.get("sentiment", 0) > 0:
            with st.expander("🔎 Strategic Perception Analysis", expanded=True):
                data = st.session_state.perception
                # Convert the 20-point score to a 100-point scale
                score_20 = data.get('strategic_perception_score', 0)
                score_100 = round(score_20 * 5, 2)
                st.metric(
                    label="Overall Perception Score",
                    value=f"{score_100} / 100"
                )
                st.write(f"**Verdict:** `{data.get('verdict', 'N/A')}`")
                st.markdown("---")

                col1, col2 = st.columns(2)
                col1.metric("Market Sentiment Score", f"{data.get('market_sentiment_score', 0):.2f} / 10")
                col2.metric("Management Quality Score", f"{data.get('management_quality_score', 0):.2f} / 10")

                # Display notes and headlines
                notes = data.get('management_notes', [])
                if notes:
                    st.markdown("**Management Notes:**")
                    for note in notes:
                        st.caption(f"📝 {note}")

                headlines = data.get('sample_headlines', [])
                if headlines:
                    st.markdown("**Sample Headlines Analyzed:**")
                    for headline in headlines:
                        st.caption(f"- {headline}")

        # Only show News & Geopolitical Risk if its weight is not zero
        if st.session_state.risk and weights.get("news", 0) > 0:
            with st.expander("🛡️ News & Geopolitical Risk", expanded=True):
                data = st.session_state.risk
                if "error" in data:
                    st.error(f"Analysis Failed: {data['error']}")
                else:
                    st.metric(label="Risk Score", value=f"{data.get('risk_score', 0):.1f}/100")
                    st.markdown(f"**Verdict:** `{data.get('verdict', 'N/A')}`")
                    st.markdown("**Recent Risk Headlines:**")
                    # Show fallback note if present
                    note = data.get("note")
                    if note:
                        st.info(note)
                    headlines = data.get("headlines", [])
                    if headlines:
                        # Handle both list of dicts (risky) and list of strings (fallback)
                        if isinstance(headlines[0], dict):
                            for h in headlines[:3]:
                                st.markdown(f"- {h.get('headline', str(h))}")
                        else:
                            for h in headlines[:3]:
                                st.markdown(f"- {h}")
                    else:
                        st.info("No headlines found. (Debug: headlines field is empty or missing)")
                        # Debug: Show the raw data for troubleshooting
                        with st.expander("Show raw news risk data (debug)"):
                            st.write(data)

        # Display the final investment decision
        if "final_score" in st.session_state and st.session_state.final_score is not None:
            st.markdown("### 📌 Final Investment Decision")
            weights = st.session_state.final_weights
            st.caption(f"Calculated with weights: FA {weights['fa']}%, TA {weights['ta']}%, Strategic Perception {weights['sentiment']}%, News {weights['news']}%")
            st.markdown(f"- **Combined Score**: {st.session_state.final_score}/100\n- **Verdict**: **{st.session_state.final_verdict}**")
# =============================================================================
# END OF REPLACEMENT BLOCK 1
# =============================================================================

# In app/main.py, inside the report generation section

elif st.session_state.get("chat_mode") == "report":
    st.subheader("📄 Report Generator")
    
    # --- UI Controls for Report ---
    st.markdown('<div class="report-selectbox-wrapper">', unsafe_allow_html=True)
    exchange = st.selectbox("Select Exchange", ["NSE", "HKEX", "NYSE", "LSE", "TSE"], key="report_exchange")
    tickers = get_top_50_tickers(exchange)
    selected_ticker = st.selectbox("Choose a Stock", tickers, key="report_ticker")
    basis = st.radio("Select Data Basis", ["Quarterly", "Annual"], horizontal=True, key="report_basis")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Generate Report", key="generate_report_btn"):
        with st.spinner(f"📊 Generating {basis.lower()} report for {selected_ticker}..."):
            try:
                # --- 1. Fetch ALL analysis data ---
                # We reuse the cached functions to get data instantly if already analyzed
                ta = get_technical_analysis(selected_ticker, basis=basis.lower())
                fa = get_fundamental_analysis(selected_ticker, basis=basis.lower())
                sentiment = get_perception_analysis(selected_ticker)
                news_risk = get_news_risk_analysis(selected_ticker, basis=basis.lower())

                # Check for errors in any module
                errors = [f"{mod}: {data['error']}" for mod, data in [("TA", ta), ("FA", fa), ("Sentiment", sentiment), ("News", news_risk)] if "error" in data]
                if errors:
                    st.error("Could not generate report due to analysis errors:\n- " + "\n- ".join(errors))
                else:
                    # --- 2. Calculate Final Score & Verdict (using a fixed model for reports) ---
                    # Note: We are not using the user-customizable weights here for consistency in reports.
                    piotroski_score = int(fa.get("Piotroski F-Score", "0/9").split('/')[0])
                    upside_score = float(fa.get("Upside", "0%").replace('%', ''))
                    
                    # A simple, fixed scoring model for the report
                    fundamental_score = (piotroski_score / 9) * 50 + min(upside_score, 100) / 2
                    final_score = (0.4 * fundamental_score + 
                                   0.3 * ta["ta_score"] +
                                   0.2 * sentiment["score"] * 10 +
                                   0.1 * (100 - news_risk["risk_score"]))
                    
                    final_verdict = ("Strong Buy" if final_score >= 80 else "Buy" if final_score >= 65 else "Hold" if final_score >= 50 else "Sell")

                    # --- 3. Gather Stock Info ---
                    stock_info = {
                        "ticker": selected_ticker,
                        "name": yf.Ticker(selected_ticker).info.get("shortName", ""),
                        "price": yf.Ticker(selected_ticker).info.get("currentPrice", "N/A"),
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "basis": basis
                    }

                    # --- 4. Call the Report Generators ---
                    pdf_data = generate_pdf_report(
                        stock_info, ta, fa, sentiment, news_risk, final_score, final_verdict
                    )
                    
                    # Consolidate all data for CSV
                    csv_report_data = {**stock_info, **ta, **fa, **sentiment, **news_risk, "final_score": final_score, "final_verdict": final_verdict}
                    csv_data = generate_csv_report([csv_report_data])

                    st.success(f"✅ Report for {selected_ticker} generated successfully!")
                    
                    # --- 5. Display Download Buttons ---
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button("📥 Download PDF Report", data=pdf_data, file_name=f"{selected_ticker}_report.pdf", mime="application/pdf")
                    with col2:
                        st.download_button("📥 Download CSV Data", data=csv_data, file_name=f"{selected_ticker}_data.csv", mime="text/csv")

            except Exception as e:
                logging.error(f"Report generation failed for {selected_ticker}: {e}", exc_info=True)
                st.error(f"An unexpected error occurred during report generation: {str(e)}")