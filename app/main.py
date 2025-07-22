# main.py
import streamlit as st
import yfinance as yf
import streamlit.components.v1 as components
import concurrent.futures
import os
import sys
import pandas as pd
from datetime import datetime
import logging
import importlib

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# =============================================================================
# --- CONFIGURATION (MUST BE AT THE TOP) ---
# =============================================================================
st.set_page_config(page_title="StockMatrix", layout="centered")
### ADD THIS ENTIRE BLOCK ###
import plotly.graph_objects as go
def initialize_session_state():
    """Initializes all required keys in the session state (our whiteboard)."""
    # These are the "sections" of our whiteboard.
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
        "risk": None,
        "pdf_report": None,
    }
    for key, value in STATE_KEYS.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # State for the chat assistant (it also uses the whiteboard!)
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hi! Ask me to analyze a stock or compare stocks."}]

# Call the function immediately to set everything up
initialize_session_state()

def reset_analysis_data():
    """This is our 'eraser' for when the user types a new stock ticker."""
    st.session_state.stock_data = None
    st.session_state.stock_info = None
    # ... reset all other keys ...
    
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# --- Custom CSS for Streamlit ---
st.markdown("""
    <div class="top-banner">
        🪙<span id="stockmatrix-title">StockMatrix</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("""
    <style>
    body {
        background: #FAFAFA !important; /* Off-White Neutral */
        min-height: 100vh;
        color: #1A1A1A !important; /* Almost Black for main text */
    }
    .stApp {
        background: #FAFAFA !important;
        min-height: 100vh;
        color: #1A1A1A !important;
    }
    .top-banner {
        padding: 10px 20px;
        font-size: 44px;
        font-weight: 900;
        position: sticky;
        top: 0;
        z-index: 999;
        background: linear-gradient(90deg, #0A1F44 60%, #FFD700 100%);
        text-shadow: none !important;
        box-shadow: 0 2px 8px rgba(10, 31, 68, 0.12);
        border-radius: 0 0 18px 18px;
        letter-spacing: 1px;
        border-bottom: 1px solid #0A1F44;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .curated-footer {
        text-align: right;
        font-size: 15px;
        color: #FFD700;
        font-weight: 700;
        letter-spacing: 0.5px;
        padding: 10px 20px;
    }
    .block-container {
        background: #FFFFFF;
        border-radius: 18px;
        padding: 24px;
        box-shadow: 0 4px 32px rgba(10, 31, 68, 0.10);
        color: #1A1A1A !important;
    }
    /* Make all markdown and widget text visible */
    .stMarkdown, .stText, .stExpander, .stDataFrame, .stRadio, .stSelectbox, .stButton, .stSlider, .stDownloadButton, .stChatInputContainer, .stChatMessage, .stChatInput, .stTextInput, .stTextArea, .stSelectbox > div, .stSelectbox label, .stRadio label, .stExpanderHeader, .stExpanderContent, .stAlert, .stSubheader, .stHeader, .stCaption, .stTable, .stDataFrame, .stCheckbox label {
        color: #1A1A1A !important;
    }
    /* Ensure all text inside expanders is visible (fix for all analysis blocks) */
    .stExpanderContent, .stExpanderContent * {
        color: #1A1A1A !important;
    }
    div[data-testid="stCaptionContainer"] {
        color: #31333F !important; /* Dark grey for readable captions */
    }
    /* Headline and subheader text */
    .stHeader, .stSubheader, h1, h2, h3, h4, h5, h6 {
        color: #000000 !important;
        font-weight: 900 !important;
        /* Remove all shadows and effects */
        text-shadow: none !important;
        letter-spacing: normal !important;
    }
    /* Chat input bar and send button - THEME UPDATE */
    section[data-testid="stChatInput"],
    .stChatInputContainer,
    div[data-testid="stChatInput"] {
        background: #F0F0F0 !important;            /* Light grey outer container */
        border-radius: 20px !important;
        padding: 6px !important;
        border: none !important;
        box-shadow: none !important;
        margin-bottom: 24px !important;
        display: flex !important;
        align-items: center !important;
    }
    section[data-testid="stChatInput"] {
        background-color: #F0F0F0 !important;
    }
    
    section[data-testid="stChatInput"] input,
    .stChatInputContainer input,
    div[data-testid="stChatInput"] input {
        background: #1E1E25 !important;          /* Dark input box */
        color: #FFFFFF !important;               /* White typing text */
        border: none !important;
        font-size: 18px !important;
        font-weight: 500 !important;
        border-radius: 12px !important;
        padding: 8px 12px !important;
    }
    section[data-testid="stChatInput"] input::placeholder {
        color: #CCCCCC !important;
        opacity: 0.8;
    }
    section[data-testid="stChatInput"] button,
    .stChatInputContainer button,
    div[data-testid="stChatInput"] button {
        background: #FFFFFF !important;          /* White send button */
        color: #0A1F44 !important;               /* Navy arrow */
        border-radius: 12px !important;
        border: none !important;
        font-weight: bold !important;
        box-shadow: none !important;
    }
    section[data-testid="stChatInput"] button:hover,
    .stChatInputContainer button:hover,
    div[data-testid="stChatInput"] button:hover {
        background: #5F4B8B !important; /* Royal Purple for hover */
        color: #FFD700 !important;
        border: 2px solid #5F4B8B !important;
    }
    /* Expander header color and icon */
    .stExpanderHeader {
        color: #000000 !important;
        font-weight: 600;
        font-size: 18px;
        position: relative;
        padding-left: 28px !important;
        text-shadow: none !important;
    }
    .stExpanderHeader:before {
        color: #000000 !important;
        /* Remove gold icon color */
    }
    /* Expander background and border */
    .stExpander {
        background: #FAFAFA !important;
        border-radius: 12px !important;
        border: 1px solid #000000 !important;
        margin-bottom: 12px !important;
        box-shadow: none !important;
    }
    /* Remove gold outline from expander content */
    .stExpanderContent {
        border: none !important;
    }
    /* Streamlit button style: grey background, black text */
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(90deg, #FFD700 80%, #FFC300 100%) !important;
        color: #1A1A1A !important;
        border: none !important;
        font-weight: bold !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 8px rgba(10, 31, 68, 0.10) !important;
        transition: background 0.2s, color 0.2s !important;
    }
    section[data-testid="stChatInput"] *:focus {
        outline: none !important;
        box-shadow: none !important;
    }

    /* Button hover state */
    .stButton > button:hover, .stDownloadButton > button:hover {
        background: #FFEA70 !important;
        color: #0A1F44 !important;
    }

    /* Button disabled state */
    .stButton > button:disabled, .stDownloadButton > button:disabled {
        background: #FFF8DC !important;
        color: #888888 !important;
        opacity: 1 !important;
    }
    /* Force black/dark font for all Streamlit alert messages */
    .stAlert {
        color: #1A1A1A !important;
    }

    /* Also ensure inner divs don’t override it */
    .stAlert > div {
        color: #1A1A1A !important;
    }

    /* Links */
    a {
        color: #5F4B8B !important; /* Royal Purple for links */
    }
    /* Make all markdown text visible */
    .stMarkdown p, .stMarkdown ul, .stMarkdown li, .stMarkdown span, .stMarkdown strong, .stMarkdown em {
        color: #1A1A1A !important;
    }
    /* Highlighted inline code in Quick Tips expander */
    .stExpander .stMarkdown code {
        background: #FFD700 !important;
        color: #0A1F44 !important;
        border-radius: 6px !important;
        font-weight: 700;
        font-size: 1em;
        padding: 2px 8px !important;
        box-shadow: 0 1px 4px 0 rgba(10, 31, 68, 0.10);
    }
    /* Remove white bar at bottom (footer) */
    footer, .st-emotion-cache-1v0mbdj, .st-emotion-cache-1avcm0n {
        background: transparent !important;
        color: transparent !important;
        box-shadow: none !important;
        border: none !important;
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    /* Make all radio/checkbox/select options and labels black and bold */
    .stRadio label, .stRadio span, .stRadio div, 
    .stCheckbox label, .stCheckbox span, .stCheckbox div,
    .stSelectbox label, .stSelectbox span, .stSelectbox div,
    .stSlider label, .stSlider span, .stSlider div {
        color: #000000 !important;
        font-weight: 700 !important;
    }
    /* Light gray selectbox (dropdown) styling */
    .stSelectbox label {
        color: #1A1A1A !important;
        font-weight: 700 !important;
    }

    .stSelectbox div[data-baseweb="select"] > div {
        background: #F0F0F0 !important;   /* Light gray dropdown field only */
        color: #1A1A1A !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
    }

    .stSelectbox div[data-baseweb="select"] > div {
        background: #F0F0F0 !important;   /* Light gray for dropdown */
        color: #1A1A1A !important;
        border-radius: 12px !important;
    }

    /* Remove selectbox focus/active border and shadow */
    .stSelectbox > div:focus-within, .stSelectbox > div:active, .stSelectbox > div[data-baseweb="select"]:focus-within, .stSelectbox > div[data-baseweb="select"]:active {
        box-shadow: none !important;
        border: none !important;
        outline: none !important;
    }
    .stSelectbox > div, .stSelectbox div[data-baseweb="select"] > div {
        border: none !important;
        outline: none !important;
    }
    /* --- Remove background & spacing from radio buttons --- */
    div[data-testid="stSelectbox"] > div:first-child {
        background: transparent !important;
        padding: 0 !important;
        margin: 0 !important;
        box-shadow: none !important;
    }
    .ra-selectbox-wrapper h4 {
        margin-bottom: 4px !important;
        margin-top: 2px !important;
    }
    .ra-selectbox-wrapper div[data-testid="stRadio"] {
        margin-top: 0px !important;
        margin-bottom: 4px !important;
        padding: 0 !important;
    }
    
    /* Fix spacing ONLY inside Run Analysis section */
    .ra-selectbox-wrapper div[data-testid="stSelectbox"] {
        margin-top: 0px !important;
        margin-bottom: 6px !important;
        padding-top: 0px !important;
    }
    .ra-selectbox-wrapper > div {
    margin: 0px !important;
    padding: 0px !important;
    }

    /* Fix spacing ONLY inside report section */
    .report-selectbox-wrapper div[data-testid="stSelectbox"] {
        margin-top: 8px !important;
        margin-bottom: 16px !important;
        padding-top: 0px !important;
    }
    #stockmatrix-title {
        color: #FFFFFF !important;
        font-size: 44px !important;
        font-weight: 900 !important;
        text-shadow: none !important;
        display: inline;
    }
    /* 🔧 Force background of full chat zone (message + input area) */
    div[data-testid="stChatMessageGroup"] {
        background-color: #F0F0F0 !important;
        padding: 16px !important;
        border-top: 2px solid #E0E0E0;
    }

    /* --- Ensure all metric text is visible (fix invisible metric text) --- */
    .stMetric, .stMetricLabel, .stMetricValue, .stMetricDelta, .stMetricContainer, .stMetric > div {
        color: #1A1A1A !important;
        font-weight: 700 !important;
    }
    /* Also fix for metric blocks inside expanders */
    .stExpander .stMetric, .stExpander .stMetricLabel, .stExpander .stMetricValue {
        color: #1A1A1A !important;
    }
    /* Ensure subheaders and verdicts are visible */
    .stExpander .stSubheader, .stExpander h2, .stExpander h3, .stExpander h4 {
        color: #1A1A1A !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='curated-footer' style='color: #000000;'>Curated and powered by Kushagra Bansal</div>", unsafe_allow_html=True)



import logging
logging.basicConfig(level=logging.DEBUG)
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
def get_sentiment_analysis(ticker, basis: str = "annual"):
    return sentiment_mod.analyze_sentiment(ticker, basis=basis.lower())

@st.cache_data(ttl=1800)
def get_news_risk_analysis(ticker, basis: str = "annual"):
    return news_mod.fetch_news_risk(ticker, basis=basis.lower())

# Increase cache times and add hash_funcs for yfinance objects
@st.cache_resource(ttl=86400)
def get_yf_info(ticker):
    import yfinance as yf
    return yf.Ticker(ticker).info

@st.cache_resource(ttl=86400)
def get_stock_history(ticker, period="6mo"):
    return yf.Ticker(ticker).history(period=period)

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
    
    st.session_state.chat_history.append({"role": "assistant", "content": greeting_msg})
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
    basis = st.radio("Select Analysis Period", ["Quarterly", "Annual"],
                    horizontal=True, key="screener_basis")
    
    st.markdown("**Choose an exchange**")
    exchange = st.selectbox("", 
                          ["NSE", "HKEX", "NYSE", "LSE", "TSE"], 
                          key="screener_exchange")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        min_upside = col1.slider("Minimum DCF Upside (%)", -50, 200, 20)
    with col2:
        min_ta = st.slider("Minimum TA Score", 0, 100, 50)
    with col3:
        max_vol = st.slider("Volatility Threshold (Annualized %)", 0, 100, 50)


# In main.py, inside the "screener" block

# ... (after the sliders)

    if st.button("🔍 Find Stocks", key="screener_button"):
        tickers = get_top_50_tickers(exchange)
        with st.spinner(f"Screening stocks on {exchange}..."):
            # --- FIX: ADDED THE MISSING CALL TO THE SCREENER ENGINE ---
            results = screener_engine.screen_stocks(
                tickers=tickers,
                min_upside=min_upside,
                min_ta=min_ta,
                max_volatility=max_vol
            )
            # Store results in session state to persist
            st.session_state.screener_results = results
    else:
        # Ensure results from previous runs are still displayed
        results = st.session_state.get("screener_results", [])


    # Display results
    if results:
        st.markdown(f"#### ✅ {len(results)} stocks matched your criteria.")
        df = pd.DataFrame(results)

        # --- FIX: CORRECTED THE STYLING FUNCTION ---
        def highlight_cells(row):
            # Default style
            styles = ['' for _ in row]
            # Highlight Upside
            try:
                upside_val = float(str(row['Upside (%)']).replace('%', ''))
                if upside_val >= 50:
                    styles[1] = 'background-color: #d4edda; color: #155724;' # Green
                elif upside_val >= 20:
                    styles[1] = 'background-color: #fff3cd; color: #856404;' # Yellow
            except (ValueError, TypeError):
                pass # Ignore if not a number

            # Highlight TA Score
            try:
                ta_score = row['TA Score']
                if ta_score >= 70:
                    styles[2] = 'background-color: #d4edda; color: #155724;' # Green
            except (ValueError, TypeError):
                pass

            # Highlight Volatility (lower is better)
            try:
                vol_val = row['Volatility (%)']
                if vol_val > 75:
                    styles[3] = 'background-color: #f8d7da; color: #721c24;' # Red
            except (ValueError, TypeError):
                pass

            return styles

        # Apply the styling
        styled_df = df.style.apply(highlight_cells, axis=1).format({
            "Upside (%)": "{:.2f}%",
            "TA Score": "{:.2f}",
            "Volatility (%)": "{:.2f}%"
        })

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            height=min(len(df) * 40 + 40, 600) # Dynamic height
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
        weights["sentiment"] = st.slider("Sentiment Analysis (%)", 0, 100, weights["sentiment"], key="leaderboard_sentiment_slider")
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
            df = leaderboard_engine.get_leaderboard(exchange, category="All") # Fetch all data
            if df is not None and not df.empty:
                st.session_state.leaderboard_df = df
            else:
                st.session_state.leaderboard_df = None # Clear old data on error
                st.success("Leaderboard data refreshed successfully!")
    if 'leaderboard_df' in st.session_state and st.session_state.leaderboard_df is not None:
        st.markdown("###  Leaderboard Results")
        st.dataframe(st.session_state.leaderboard_df, use_container_width=True, hide_index=True)
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
    with st.expander("🎛️ Customize Scoring Model"):
        st.markdown("Adjust the weights for each analysis category. **They must add up to 100%.**")

        if 'user_weights' not in st.session_state:
            st.session_state.user_weights = {"fa": 35, "ta": 35, "sentiment": 20, "news": 10}

        weights = st.session_state.user_weights
        weights["fa"] = st.slider("Fundamental Analysis (%)", 0, 100, weights["fa"], key="analysis_fa_slider")
        weights["ta"] = st.slider("Technical Analysis (%)", 0, 100, weights["ta"], key="analysis_ta_slider")
        weights["sentiment"] = st.slider("Sentiment Analysis (%)", 0, 100, weights["sentiment"], key="analysis_sentiment_slider")
        weights["news"] = st.slider("News & Risk Analysis (%)", 0, 100, weights["news"], key="analysis_news_slider")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        auto_refresh = st.checkbox("🔄 Auto-refresh every 30 seconds", key="auto_refresh_checkbox")

        if st.button("Stock Price", key="run_analysis_price_btn") or (st.session_state.get("auto_refresh_checkbox") and st.session_state.get("auto_refreshing")):
            st.session_state.auto_refreshing = auto_refresh
            try:
                stock = yf.Ticker(selected_ticker)
                info = stock.info
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

                hist = get_stock_history(selected_ticker, period="6mo")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Close Price"))
                fig.update_layout(title="Price Trend (6 Months)", xaxis_title="Date", yaxis_title=f"Price ({currency})")
                st.plotly_chart(fig)

                if auto_refresh:
                    # This code injects an HTML tag to refresh the page every 30 seconds
                    # without freezing the Python script.
                    components.html(
                        """
                        <meta http-equiv="refresh" content="30">
                        """,
                        height=0, # Make the HTML component invisible
                    )
                # --------------------

            except Exception as e:
                st.error(f"Error fetching stock data: {str(e)}")

    with col2:
        analysis_type = st.radio("Select Analysis Type", ["Technical", "Fundamental", "Both"], key="analysis_type")

        total_weight = sum(st.session_state.user_weights.values())
        is_disabled = (total_weight != 100)

## REPLACE WITH THIS NEW LOGIC

        if st.button("Run Analysis", key="run_analysis_btn", disabled=is_disabled):
            reset_analysis_data()
            with st.spinner(f"🔍 Running {basis.lower()} analysis for {selected_ticker}..."):
                try:
                    # --- ACTION: Fetch data and SAVE to the whiteboard ---
                    st.session_state.technicals = get_technical_analysis(selected_ticker, basis=basis.lower())
                    st.session_state.fundamentals = get_fundamental_analysis(selected_ticker, basis=basis.lower())
                    st.session_state.sentiment = get_sentiment_analysis(selected_ticker, basis=basis.lower())
                    st.session_state.risk = get_news_risk_analysis(selected_ticker, basis=basis.lower())

                    # Also store the final score and verdict in the whiteboard
                    if "error" not in st.session_state.fundamentals and "error" not in st.session_state.technicals:
                        user_weights = st.session_state.user_weights
                        final_score = round(
                            (user_weights["fa"] / 100) * st.session_state.fundamentals.get("dcf_score", 0) +
                            (user_weights["ta"] / 100) * st.session_state.technicals.get("ta_score", 0) +
                            (user_weights["sentiment"] / 100) * st.session_state.sentiment.get("score", 0) * 10 +
                            (user_weights["news"] / 100) * st.session_state.risk.get("risk_score", 50), 2
                        )
                        final_verdict = ("Strong Buy" if final_score >= 80 else "Buy" if final_score >= 65 else "Hold" if final_score >= 50 else "Sell")

                        st.session_state.final_score = final_score
                        st.session_state.final_verdict = final_verdict
                        st.session_state.final_weights = user_weights

                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
        ## ADD THIS NEW DISPLAY SECTION

        st.divider()

        # --- DISPLAY LOGIC: This section reads from the whiteboard (st.session_state) ---

        if st.session_state.technicals:
            with st.expander("🧪 Technical Analysis", expanded=True):
                data = st.session_state.technicals
                if "error" in data:
                    st.error(f"Analysis Failed: {data['error']}")
                else:
                    st.metric(label="Technical Score", value=f"{data.get('ta_score', 0)}/100")
                    st.write(f"**Verdict:** `{data.get('verdict', 'N/A')}`")
                    # ... you can add more details here if you want ...

        # In main.py, find the expander for displaying fundamental analysis results

        if st.session_state.fundamentals:
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

        # Add similar display blocks for sentiment and risk
        if st.session_state.sentiment:
            with st.expander("💬 Sentiment Analysis", expanded=True):
                data = st.session_state.sentiment
                if "error" in data:
                    st.error(f"Analysis Failed: {data['error']}")
                else:
                    st.metric(label="Sentiment Score", value=f"{data.get('score', 0) * 10:.1f}/100")
                    st.markdown(f"**Label:** `{data.get('label', 'N/A')}`")
                    st.markdown("**Sample Headlines Used in Analysis:**")
                    for headline in data.get("labeled_headlines", [])[:3]:
                        st.markdown(f"- {headline}")

        if st.session_state.risk:
            with st.expander("🛡️ News & Geopolitical Risk", expanded=True):
                data = st.session_state.risk
                if "error" in data:
                    st.error(f"Analysis Failed: {data['error']}")
                else:
                    st.metric(label="Risk Score", value=f"{data.get('risk_score', 0):.1f}/100")
                    st.markdown(f"**Verdict:** `{data.get('verdict', 'N/A')}`")
                    st.markdown("**Recent Risk Headlines:**")
                    for headline in data.get("headlines", [])[:3]:
                        st.markdown(f"- {headline}")

        # Display the final investment decision
        if "final_score" in st.session_state and st.session_state.final_score is not None:
            st.markdown("### 📌 Final Investment Decision")
            weights = st.session_state.final_weights
            st.caption(f"Calculated with weights: FA {weights['fa']}%, TA {weights['ta']}%, Sentiment {weights['sentiment']}%, News {weights['news']}%")
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
                sentiment = get_sentiment_analysis(selected_ticker, basis=basis.lower())
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