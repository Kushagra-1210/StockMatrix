import streamlit as st
st.markdown("""
    <style>
    .top-banner {
        color: black;
        padding: 10px 20px;
        font-size: 40px;
        font-weight: 700;
        border-bottom: 1px solid #444;
        position: sticky;
        top: 0;
        z-index: 999;
    }
    </style>
    <div class="top-banner">
        🪙StockMatrix
    </div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
footer {visibility: hidden;}
[data-testid="stAppViewContainer"]::after {
    content: "Made by Kushagra Bansal";
    position: fixed;
    bottom: 8px;
    right: 12px;
    font-size: 12px;
    color: #ccc;
}
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="STOCK ANALYSER", layout="centered")

import concurrent.futures
from functools import partial
import time
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime
import importlib


import logging
logging.basicConfig(level=logging.DEBUG)
st.set_option('client.showErrorDetails', True)
from typing import Dict, Any


from backend import technical_analysis as ta_mod
from backend import fundamental_analysis as fa_mod
from backend import sentiment_analysis as sentiment_mod
from backend import news_risk_analyzer as news_mod

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
        - 💡 **Get Investment Insights**

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
            "- Insight Generation (IG)\n"
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
    
    exchange = st.selectbox("Select Exchange", 
                          ["NSE", "HKEX", "NYSE", "LSE", "TSE"], 
                          key="screener_exchange")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        min_fa = st.slider("Minimum FA Score", 0, 100, 50)
    with col2:
        min_ta = st.slider("Minimum TA Score", 0, 100, 50)
    with col3:
        max_vol = st.slider("Max Volatility %", 0, 100, 50)

        
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
                    fa["fa_score"] >= min_fa and 
                    ta["ta_score"] >= min_ta and 
                    vol <= max_vol):
                    return {
                        "Ticker": ticker,
                        "FA Score": fa["fa_score"],
                        "TA Score": ta["ta_score"],
                        "Volatility": f"{vol}%",
                        "Verdict": fa["verdict"]
                    }
            except Exception as e:
                st.warning(f"Skipped {ticker}: Error in processing")
                return None

        # Process all tickers in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
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
        if results:
            st.success(f"✅ {len(results)} stocks matched your criteria.")
            df = pd.DataFrame(results)
            
            # Enhanced styling function
            def background_color(row):
                colors = []
                for val in row:
                    if isinstance(val, (int, float)):
                        # FA Score (Green gradient)
                        if row.name == 'FA Score':
                            intensity = min(255, int(255 * (val/100)))
                            colors.append(f'background-color: rgba(0, 255, 0, {intensity/255})')
                        # TA Score (Blue gradient)
                        elif row.name == 'TA Score':
                            intensity = min(255, int(255 * (val/100)))
                            colors.append(f'background-color: rgba(0, 0, 255, {intensity/255})')
                        # Volatility (Red gradient - reversed)
                        elif row.name == 'Volatility':
                            volatility = float(str(val).replace('%',''))
                            intensity = min(255, int(255 * (1 - volatility/100)))
                            colors.append(f'background-color: rgba(255, 0, 0, {intensity/255})')
                        else:
                            colors.append('')
                    else:
                        # Verdict text coloring
                        if row.name == 'Verdict':
                            if 'Undervalued' in val:
                                colors.append('background-color: #90EE90')  # Light green
                            elif 'Fair' in val:
                                colors.append('background-color: #ADD8E6')  # Light blue
                            else:
                                colors.append('')
                        else:
                            colors.append('')
                return colors
            
            # Apply styling with improved performance
            styled_df = df.style.apply(background_color, axis=0)\
                              .format({'Volatility': "{:.2f}%"})\
                              .set_properties(**{'text-align': 'center'})
            
            # Optimized display
            st.markdown(styled_df.to_html(), unsafe_allow_html=True)
            
            # Add download button
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Results as CSV",
                data=csv,
                file_name=f"{exchange}_screener_results.csv",
                mime="text/csv"
            )
        else:
            st.warning("⚠️ No stocks matched the given filters.")

elif st.session_state.get("chat_mode") == "stock_leaderboard":
    if st.button("← Back to Main Menu"):
        st.session_state.chat_mode = None
        st.rerun()

    st.subheader("Stock Leaderboard")

    # Analysis period first
    basis = st.radio("Select Analysis Period", ["Quarterly", "Annual"], 
                    horizontal=True, key="leaderboard_basis")
    
    # Then stock exchange
    exchange = st.selectbox(
        "Select Stock Exchange",
        ["NSE", "NYSE", "TSE", "LSE", "HKEX"],
        key="leaderboard_exchange"
    )   
    
    # Data computation with proper initialization
# REMOVE the manual data list building and replace with:
    if st.button("🔄 Compute/Refresh Data"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def process_leaderboard_ticker(ticker, i, total):
            status_text.text(f"Processing {i+1}/{total}")
            progress_bar.progress((i+1)/total)
            try:
                ta = get_technical_analysis(ticker, basis.lower())
                fa = get_fundamental_analysis(ticker, basis.lower())
                sentiment = get_sentiment_analysis(ticker, basis.lower())
                vol = calculate_volatility(ticker)
                return {
                    "Ticker": ticker,
                    "FA Score": fa["fa_score"],
                    "TA Score": ta["ta_score"],
                    "Sentiment": sentiment["score"] * 10,
                    "Volatility": vol,
                    "Final Score": round(0.35*fa["fa_score"] + 0.35*ta["ta_score"] + 0.2*sentiment["score"]*10 + 0.1*(100-vol), 2)
                }
            except Exception:
                return None

        with concurrent.futures.ThreadPoolExecutor() as executor:
            tickers = get_top_50_tickers(exchange)
            processed = list(filter(None, [process_leaderboard_ticker(t, i, len(tickers)) 
                            for i, t in enumerate(tickers)]))
            st.session_state.leaderboard_df = pd.DataFrame(processed)

    # Display section with proper null checks
    if "leaderboard_df" in st.session_state:
        df = st.session_state.leaderboard_df
        
        # Check if df is None or empty
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
                st.dataframe(df.nlargest(5, "FA Score"))

            with st.expander("Top 5 Low Risk (Volatility)"):
                st.dataframe(df.nsmallest(5, "Volatility"))

            with st.expander("Top 5 Negative Sentiment"):
                st.dataframe(df.nsmallest(5, "Sentiment"))
    else:
        st.warning("Leaderboard data not initialized. Please compute scores.")

elif st.session_state.get("chat_mode") == "insight_generation":
    if st.session_state.show_insight_buttons:
        st.markdown("#### What do you want to do?")
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

elif st.session_state.get("chat_mode") == "run_analysis":
    st.subheader("🧪 Run Analysis Module")
    
    # Basis selection at the top (applies to all analyses)
    basis = st.radio("Select Data Basis", ["Quarterly", "Annual"], 
                    horizontal=True, key="run_analysis_basis")

    st.subheader("1. Select Stock Exchange")
    exchange = st.selectbox("Choose an exchange:", 
                          options=["NSE", "HKEX", "NYSE", "LSE", "TSE"], 
                          key="run_analysis_exchange")

    if exchange:
        tickers = get_top_50_tickers(exchange)
        selected_ticker = st.selectbox("2. Choose a Stock", tickers, 
                                     key="run_analysis_ticker")

        col1, col2 = st.columns(2)
        with col1:
            auto_refresh = st.checkbox("🔄 Auto-refresh every 30 seconds", 
                                     key="auto_refresh_checkbox")

            if st.button("Stock Price", key="run_analysis_price_btn") or st.session_state.get("auto_refreshing"):
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
                    fig.update_layout(title="Price Trend (6 Months)", 
                                    xaxis_title="Date", 
                                    yaxis_title=f"Price ({currency})")
                    st.plotly_chart(fig)

                    if auto_refresh:
                        time.sleep(30)
                        st.experimental_rerun()

                except Exception as e:
                    st.error(f"Error fetching stock data: {str(e)}")

        with col2:
            analysis_type = st.radio("Select Analysis Type", 
                                   ["Technical", "Fundamental", "Both"], 
                                   key="analysis_type")

            if st.button("Run Analysis", key="run_analysis_btn"):
                with st.spinner(f"🔍 Running {basis.lower()} analysis..."):
                    try:
                        # Refresh options
                        refresh_tech = st.checkbox("🔄 Refresh Technical Analysis", 
                                                 key="refresh_technical")
                        refresh_fund = st.checkbox("🔄 Refresh Fundamental Analysis", 
                                                 key="refresh_fundamental")
                        refresh_sent = st.checkbox("🔄 Refresh Sentiment Analysis", 
                                                 key="refresh_sentiment")
                        refresh_news = st.checkbox("🔄 Refresh News & Risk Analysis", 
                                                 key="refresh_news")

                        # Get analysis data with basis parameter
                        ta = get_technical_analysis(selected_ticker, basis=basis.lower()) if not refresh_tech else ta_mod.analyze_technical_indicators(selected_ticker, basis=basis.lower())
                        fa = get_fundamental_analysis(selected_ticker, basis=basis.lower()) if not refresh_fund else fa_mod.analyze_fundamentals(selected_ticker, basis=basis.lower())
                        sentiment = get_sentiment_analysis(selected_ticker, basis=basis.lower()) if not refresh_sent else sentiment_mod.analyze_sentiment(selected_ticker, basis=basis.lower())
                        news_risk = get_news_risk_analysis(selected_ticker, basis=basis.lower()) if not refresh_news else news_mod.fetch_news_risk(selected_ticker, basis=basis.lower())

                        # Display results
                        if analysis_type == "Technical":
                            st.subheader(f"🧪 Technical Analysis Report ({basis})")
                            if "error" in ta:
                                st.error(ta["error"])
                            else:
                                st.markdown(f"""
                                - **Current Price**: {ta['current_price']}  
                                - **RSI (14)**: {ta['rsi']}  
                                - **SMA-20**: {ta['sma_20']}  
                                - **EMA-20**: {ta['ema_20']}  
                                - **TA Score**: {ta['ta_score']}/100  
                                - **Verdict**: **{ta['verdict']}**
                                """)
                                st.markdown('<p style="font-size: 10px; color: grey;">Source: Yahoo Finance (historical data)</p>', unsafe_allow_html=True)
                                if "ta_breakdown" in ta:
                                    st.markdown("##### 🔍 Technical Score Breakdown")
                                    for factor, value in ta["ta_breakdown"].items():
                                        st.markdown(f"- **{factor}**: {value}")

                        elif analysis_type == "Fundamental":
                            st.subheader(f"📊 Fundamental Analysis Report ({basis})")
                            if "error" in fa:
                                st.error(fa["error"])
                            else:
                                fcf = fa.get("fcf", "N/A")
                                fcf_disp = f"{fcf:,}" if isinstance(fcf, (int, float)) else "N/A"
                                st.markdown(f"""
                                - **Market Cap**: {fa['market_cap']:,} ({fa['size']})  
                                - **EPS**: {fa['eps']}  
                                - **ROE**: {fa['roe']}%  
                                - **PE Ratio**: {fa['pe_ratio']}  
                                - **Debt-to-Equity**: {fa['de_ratio']}  
                                - **Free Cash Flow**: {fcf_disp}
                                - **Data As of**: {fa['fiscal_date']}  
                                - **FA Score**: {fa['fa_score']}/100  
                                - **Verdict**: **{fa['verdict']}**
                                """)
                                st.markdown('<p style="font-size: 10px; color: grey;">Source: Yahoo Finance (via yfinance)</p>', unsafe_allow_html=True)
                                if "fa_breakdown" in fa:
                                    st.markdown("##### 🔍 Fundamental Score Breakdown")
                                    for factor, value in fa["fa_breakdown"].items():
                                        st.markdown(f"- **{factor}**: {value}")

                        elif analysis_type == "Both":
                            st.subheader(f"📊 Combined Analysis Report ({basis})")
                            
                            if any(mod is None or (isinstance(mod, dict) and "error" in mod) for mod in [ta, fa]):
                                st.error("❌ One or more critical modules failed. Please try again.")

                            else:
                                # Optional warnings for Sentiment and News
                                if sentiment is None or (isinstance(sentiment, dict) and "error" in sentiment):
                                    st.warning("⚠️ Sentiment analysis unavailable.")
                                if news_risk is None or (isinstance(news_risk, dict) and "error" in news_risk):
                                    st.warning("⚠️ News risk analysis couldn't be completed — the API limit has been reached, Try again later!")
                            
                                # Technical Analysis Section
                                st.markdown("### 🧪 Technical Analysis")
                                st.markdown(f"""
                                - **Current Price**: {ta['current_price']}  
                                - **RSI (14)**: {ta['rsi']}  
                                - **SMA-20**: {ta['sma_20']}  
                                - **EMA-20**: {ta['ema_20']}  
                                - **TA Score**: {ta['ta_score']}/100  
                                - **Verdict**: **{ta['verdict']}**
                                """)
                                
                                # Fundamental Analysis Section
                                st.markdown("### 📊 Fundamental Analysis")
                                fcf = fa.get("fcf", "N/A")
                                fcf_disp = f"{fcf:,}" if isinstance(fcf, (int, float)) else "N/A"
                                st.markdown(f"""
                                - **Market Cap**: {fa['market_cap']:,} ({fa['size']})  
                                - **EPS**: {fa['eps']}  
                                - **ROE**: {fa['roe']}%  
                                - **PE Ratio**: {fa['pe_ratio']}  
                                - **Debt-to-Equity**: {fa['de_ratio']}  
                                - **Free Cash Flow**: {fcf_disp}
                                - **Data As of**: {fa['fiscal_date']}  
                                - **FA Score**: {fa['fa_score']}/100  
                                - **Verdict**: **{fa['verdict']}**
                                """)

                                # 💬 Sentiment Analysis Section
                                st.markdown("### 💬 Sentiment Analysis")
                                st.markdown(f"""
                                - **Sentiment Score**: {sentiment['score']}/10  
                                - **Label**: {sentiment['label']}
                                """)

                                # Display sample headlines if available
                                if sentiment.get("headlines"):
                                    st.markdown("**📰 Sample Headlines**")
                                    for item in sentiment["headlines"][:2]:  # Top 2
                                        st.markdown(f"- {item['title']} ({item['label']})")

                                
                                # News Risk Section
                                # 🛡️ News & Geopolitical Risk Section
                                st.markdown("### 🛡️ News & Geopolitical Risk")
                                st.markdown(f"""
                                - **Risk Score**: {news_risk.get('risk_score', 'N/A')} / 100  
                                - **Verdict**: {news_risk.get('verdict', 'N/A')}
                                """)

                                # Sample Headlines in smaller font
                                if news_risk.get("news"):
                                    st.markdown("**📰 Sample Headlines**", unsafe_allow_html=True)
                                    for article in news_risk["news"]:
                                        st.markdown(f"- {article['title']}", unsafe_allow_html=True)

                                # Final Combined Score
                                final_score = round(
                                    0.35 * fa["fa_score"] +
                                    0.35 * ta["ta_score"] +
                                    0.2 * sentiment["score"] * 10 +
                                    0.1 * news_risk["risk_score"], 2
                                )
                                final_verdict = (
                                    "Strong Buy" if final_score >= 80
                                    else "Buy" if final_score >= 65
                                    else "Hold" if final_score >= 50
                                    else "Sell"
                                )

                                st.markdown("### 📌 Final Investment Decision")
                                st.markdown(f"""
                                - **Combined Score**: {final_score}/100  
                                - **Verdict**: **{final_verdict}**
                                """)

                    except Exception as e:
                        st.error(f"Analysis failed: {str(e)}")


elif st.session_state.get("chat_mode") == "report":
    st.subheader("📄 Report Generator")
    report_mod = importlib.import_module("backend.report_generator")

    # Exchange and stock selection
    exchange = st.selectbox("Select Exchange", 
                          ["NSE", "HKEX", "NYSE", "LSE", "TSE"], 
                          key="report_exchange")
    
    if exchange:
        tickers = get_top_50_tickers(exchange)
        selected_ticker = st.selectbox("Choose a Stock", tickers, 
                                     key="report_ticker")
        
        # Basis selection with clear labels
        basis = st.radio("Select Data Basis", ["Quarterly", "Annual"],
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
                        0.35 * fa["fa_score"] +
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


