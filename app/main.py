# main.py
import streamlit as st
import yfinance as yf
import streamlit.components.v1 as components
import concurrent.futures
import time
import os
import sys
import pandas as pd
from datetime import datetime
import logging
import importlib


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
from backend import technical_analysis as ta_mod
from backend import fundamental_analysis as fa_mod
from backend import sentiment_analysis as sentiment_mod
from backend import news_risk_analyzer as news_mod
from backend.market_selector import get_top_50_tickers
from backend.screener_engine import screen_stocks, calculate_volatility
from backend.leaderboard_engine import get_leaderboard
from backend.report_generator import generate_pdf_report, generate_csv_report
from nlp.chat_router import handle_chat_command

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
    return get_risk_free_rate()

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

        def get_volatility_risk_label(vol):
            if vol < 2:
                return "🟢 Low"
            elif vol < 5:
                return "🟡 Medium"
            else:
                return "🔴 High"

        def process_ticker(ticker):
            try:
                # Get all analyses in parallel
                fa = get_fundamental_analysis(ticker, basis=basis.lower())
                ta = get_technical_analysis(ticker, basis=basis.lower())
                vol = calculate_volatility(ticker)
                
                # Check if meets all criteria
                if ("error" not in fa and 
                    "error" not in ta and 
                    vol is not None and
                    fa["upside_potential"] >= min_upside and # <-- ADD THIS LINE
                    ta["ta_score"] >= min_ta and 
                    vol <= max_vol):
                    return {
                        "Ticker": ticker,
                        "Upside (%)": fa["upside_potential"], # <-- ADD THIS LINE
                        "TA Score": ta["ta_score"],
                        "Volatility": vol,
                        "Risk Level": get_volatility_risk_label(vol),
                        "Verdict": fa["verdict"]
                    }
            except Exception:
                st.warning(f"Skipped {ticker}: Error in processing")
                return None

        # Process all tickers in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            tickers = get_top_50_tickers(exchange)
            # Process in batches for better progress tracking
            for i, result in enumerate(executor.map(process_ticker, tickers)):
                if result:  # Only append valid results
                    results.append(result)
                progress = (i + 1) / len(tickers)
                progress_bar.progress(progress)
                status_text.text(f"Processed {i+1}/{len(tickers)} tickers")
            
            progress_bar.empty()
            status_text.empty()

                    # Display results
    # Replace this section in your code (around line 550-600 where the table is displayed):

    # Display results
    # Replace the table display section (around line 550-600) with this:

    # Display results
    if results:

        st.markdown(f"<p style='color: black;'>✅ {len(results)} stocks matched your criteria.</p>", unsafe_allow_html=True)

        df = pd.DataFrame(results)
        
        # Enhanced styling function
        def background_color(row):
            colors = []
            for val in row:
                if isinstance(val, (int, float)):
                    if row.name == 'FA Score':
                        intensity = min(255, int(255 * (val/100)))
                        colors.append(f'background-color: rgba(0, 255, 0, {intensity/255})')
                    elif row.name == 'TA Score':
                        intensity = min(255, int(255 * (val/100)))
                        colors.append(f'background-color: rgba(0, 0, 255, {intensity/255})')
                    elif row.name == 'Volatility':
                        volatility = float(str(val).replace('%',''))
                        intensity = min(255, int(255 * (1 - volatility/100)))
                        colors.append(f'background-color: rgba(255, 0, 0, {intensity/255})')
                    else:
                        colors.append('')
                else:
                    if row.name == 'Verdict':
                        if 'Undervalued' in val:
                            colors.append('background-color: #90EE90')
                        elif 'Fair' in val:
                            colors.append('background-color: #ADD8E6')
                        else:
                            colors.append('')
                    else:
                        colors.append('')
            return colors
        
        # Apply styling with proper container width control
        styled_df = df.style\
            .apply(background_color, axis=0)\
            .format({'Volatility': "{:.2f}%"})\
            .set_table_styles([
                {'selector': 'table', 'props': [
                    ('width', '100%'),
                    ('max-width', '100%'),
                    ('table-layout', 'fixed'),
                    ('margin', '0 auto')
                ]},
                {'selector': 'th, td', 'props': [
                    ('text-align', 'center'),
                    ('padding', '8px'),
                    ('word-wrap', 'break-word'),
                    ('overflow', 'hidden'),
                    ('text-overflow', 'ellipsis')
                ]},
                {'selector': 'th', 'props': [
                    ('background-color', '#f2f2f2'),
                    ('font-weight', 'bold'),
                    ('font-size', '14px')
                ]},
                {'selector': 'td', 'props': [
                    ('font-size', '13px')
                ]}
            ])
        
        # Display table with proper width constraints
        st.dataframe(
            styled_df, 
            use_container_width=True,
            hide_index=True,
            height=400  # Set max height to prevent overflow
        )
        
        # Download button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Results as CSV",
            data=csv,
            file_name=f"{exchange}_screener_results.csv",
            mime="text/csv"
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

    if st.button("🔄 Compute/Refresh Data", disabled=is_leaderboard_disabled):
        progress_bar = st.progress(0)
        status_text = st.empty()

        def process_leaderboard_ticker(ticker, i, total):
            status_text.text(f"Processing {i+1}/{total}")
            progress_bar.progress((i + 1) / total)
            try:
                ta = get_technical_analysis(ticker, basis.lower())
                fa = get_fundamental_analysis(ticker, basis.lower())
                sentiment = get_sentiment_analysis(ticker, basis.lower())
                news_risk = get_news_risk_analysis(ticker, basis.lower())
                vol = calculate_volatility(ticker)

                user_weights = st.session_state.user_weights
                final_score = round(
                    (user_weights["fa"] / 100) * fa.get("dcf_score", 0) + # <-- ADD THIS
                    (user_weights["ta"] / 100) * ta.get("ta_score", 0) +
                    (user_weights["sentiment"] / 100) * sentiment.get("score", 0) * 10 +
                    (user_weights["news"] / 100) * news_risk.get("risk_score", 50), 2
                )

                return {
                    "Ticker": ticker,
                    "DCF Score": fa.get("dcf_score", 0), # <-- ADD THIS
                    "TA Score": ta.get("ta_score", 0),
                    "Sentiment": sentiment.get("score", 0) * 10,
                    "News Risk": news_risk.get("risk_score", 50),
                    "Volatility": vol,
                    "Final Score": final_score
                }
            except Exception:
                return None

        with concurrent.futures.ThreadPoolExecutor() as executor:
            tickers = get_top_50_tickers(exchange)
            processed = list(filter(None, [process_leaderboard_ticker(t, i, len(tickers)) for i, t in enumerate(tickers)]))
            st.session_state.leaderboard_df = pd.DataFrame(processed)

    if is_leaderboard_disabled:
        st.error(f"Compute button is disabled. Total weight must be 100%, but is currently {total_weight_leaderboard}%.")

    # --- DISPLAY SECTION (NO CHANGES NEEDED HERE) ---
    if "leaderboard_df" in st.session_state:
        df = st.session_state.leaderboard_df
        if df is None or df.empty:
            st.warning("No data available. Please compute scores first.")
        else:
            st.markdown("### Leaderboard Categories")
            with st.expander("Top 5 Strong Buys"):
                st.dataframe(df.nlargest(5, "Final Score"))
            with st.expander("Top 5 Bullish (TA Score)"):
                st.dataframe(df.nlargest(5, "TA Score"))
            with st.expander("Top 5 High Volatility"):
                st.dataframe(df.nlargest(5, "Volatility"))
            with st.expander("Top 5 Undervalued (FA Score)"):
                st.dataframe(df.nlargest(5, "DCF Score")) # <--- CORRECTED LINE
            with st.expander("Top 5 Low Risk (Volatility)"):
                st.dataframe(df.nsmallest(5, "Volatility"))
            with st.expander("Top 5 Negative Sentiment"):
                st.dataframe(df.nsmallest(5, "Sentiment"))
    else:
        st.warning("Leaderboard data not initialized. Please compute scores.")

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

        if st.session_state.fundamentals:
            with st.expander("📊 Fundamental Analysis (DCF Valuation)", expanded=True):
                data = st.session_state.fundamentals
                if "error" in data:
                    st.error(f"Analysis Failed: {data['error']}")
                else:
                    st.metric(
                        label="Intrinsic Value per Share (DCF)",
                        value=f"${data.get('dcf_intrinsic_value', 0):.2f}",
                        delta=f"{data.get('upside_potential', 0):.2f}% vs Current Price"
                    )
                    st.write(f"**Verdict:** `{data.get('verdict', 'N/A')}`")

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


elif st.session_state.get("chat_mode") == "report":
    st.subheader("📄 Report Generator")
    report_mod = importlib.import_module("backend.report_generator")
    
    st.markdown('<div class="report-selectbox-wrapper">', unsafe_allow_html=True)

    # Exchange and stock selection (move outside try block)
    exchange = st.selectbox(
        "Select Exchange", 
        ["NSE", "HKEX", "NYSE", "LSE", "TSE"], 
        key="report_exchange"
    )

    try:
        tickers = get_top_50_tickers(exchange)
        selected_ticker = st.selectbox("Choose a Stock", tickers, 
                                     key="report_ticker")
    
        st.markdown('<div class="report-selectbox-wrapper">', unsafe_allow_html=True)

        # Basis selection with clear labels
        st.markdown("**Select Data Basis**")
        basis = st.radio("", ["Quarterly", "Annual"],
                        horizontal=True, key="report_basis",
                        help="Quarterly: Last 3 months data | Annual: Last 12 months data")

        if st.button("Generate Report", key="generate_report_btn"):
            with st.spinner(f"📊 Generating {basis.lower()} report..."):
                try:
                    # Get all analysis data with proper basis parameter
                    ta = get_technical_analysis(selected_ticker, basis=basis.lower())
                    fa = get_fundamental_analysis(selected_ticker, basis=basis.lower())
                    sentiment = get_sentiment_analysis(selected_ticker, basis=basis.lower())
                    news_risk = get_news_risk_analysis(selected_ticker, basis=basis.lower())

                    # Error handling for each module
                    errors = []
                    if "error" in ta: errors.append(f"Technical: {ta['error']}")
                    if "error" in fa: errors.append(f"Fundamental: {fa['error']}")
                    if "error" in sentiment: errors.append(f"Sentiment: {sentiment['error']}")
                    if "error" in news_risk: errors.append(f"News Risk: {news_risk['error']}")

                    if errors:
                        st.error("Analysis Errors:\n- " + "\n- ".join(errors))

                    # Get stock info
                    stock_info = {
                        "ticker": selected_ticker,
                        "name": yf.Ticker(selected_ticker).info.get("shortName", ""),
                        "price": yf.Ticker(selected_ticker).info.get("currentPrice", "N/A"),
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "basis": basis  # Added basis to report metadata
                    }

                    # Calculate final score
                    final_score = round(
                        0.35 * fa.get("dcf_score", 0) + 
                        0.35 * ta["ta_score"] +
                        0.2 * sentiment["score"] * 10 +
                        0.1 * news_risk["risk_score"], 2
                    )
                    
                    # Determine verdict
                    final_verdict = (
                        "Strong Buy" if final_score >= 80 else
                        "Buy" if final_score >= 65 else
                        "Hold" if final_score >= 50 else "Sell"
                    )

                    # Generate reports
                    try:
                        pdf = report_mod.generate_pdf_report(
                            stock_info, ta, fa, sentiment, 
                            final_score, final_verdict, news_risk
                        )
                        
                        csv = report_mod.generate_csv_report([{
                            **ta, 
                            **fa,
                            "period": basis.lower(),
                            "sentiment_score": sentiment.get("score", "N/A"),
                            "sentiment_label": sentiment.get("label", "N/A"),
                            "news_risk_score": news_risk.get("risk_score", "N/A"),
                            "news_risk_verdict": news_risk.get("verdict", "N/A"),
                            "final_score": final_score,
                            "final_verdict": final_verdict
                        }])

                        # Success message and download buttons
                        st.success(f"✅ {basis} Report Generated Successfully!")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.download_button(
                                "📥 Download PDF", 
                                data=pdf, 
                                file_name=f"{selected_ticker}_{basis.lower()}_report.pdf", 
                                mime="application/pdf"
                            )
                        with col2:
                            st.download_button(
                                "📥 Download CSV", 
                                data=csv, 
                                file_name=f"{selected_ticker}_{basis.lower()}_report.csv", 
                                mime="text/csv"
                            )

                    except Exception as e:
                        st.error(f"Report generation failed: {str(e)}")

                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
    except Exception as e:
        st.error(f"Error initializing report section: {str(e)}")

