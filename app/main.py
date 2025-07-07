import streamlit as st
import time
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from datetime import datetime
import importlib
import concurrent.futures

import logging
logging.basicConfig(level=logging.DEBUG)
st.set_option('client.showErrorDetails', True)

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

@st.cache_data(ttl=1800)
def get_yf_info(ticker):
    return yf.Ticker(ticker).info

@st.cache_data(ttl=1800)
def get_stock_history(ticker, period="6mo"):
    return yf.Ticker(ticker).history(period=period)

# --- Path Setup ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Load Static Imports ---
from backend.market_selector import get_top_50_tickers
from nlp.chat_router import handle_chat_command
from backend.screener_engine import calculate_volatility

# --- Streamlit Config ---
st.set_page_config(page_title="STOCK ANALYSER", layout="centered")
st.title("StockMatrix")

# --- Session State Initialization ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "greeted" not in st.session_state:
    st.session_state.greeted = False
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = None
if "show_insight_buttons" not in st.session_state:
    st.session_state.show_insight_buttons = False

# --- Initial Chat Message ---
if not st.session_state.greeted:
    greeting_msg = (
        "👋 Hello! I am **StockMatrix - your AI Stock Assistant**.\n\n"
        "I analyze top 50 stocks from 5 major stock exchanges: **NSE, NYSE, LSE, HKEX, and TSE**.\n\n"
        "**What would you like to do today?**\n\n"
        "- Run Analysis\n"
        "- Generate a Report\n"
        "- Insight Generation\n\n"
        "Please type your choice below:"
    )
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

    if st.button("Run Screener", key="run_screener_btn"):
        with st.spinner(f"⏳ Screening {basis.lower()} data..."):
            tickers = get_top_50_tickers(exchange)
            results = []
            
            for ticker in tickers:
                try:
                    fa = get_fundamental_analysis(ticker, basis=basis.lower())
                    ta = get_technical_analysis(ticker, basis=basis.lower())
                    vol = calculate_volatility(ticker)

                    if "error" not in fa and "error" not in ta and vol is not None:
                        if (fa["fa_score"] >= min_fa and 
                            ta["ta_score"] >= min_ta and 
                            vol <= max_vol):
                            results.append({
                                "Ticker": ticker,
                                "FA Score": fa["fa_score"],
                                "TA Score": ta["ta_score"],
                                "Volatility": f"{vol}%",
                                "Verdict": fa["verdict"]
                            })
                except Exception:
                    continue

            if results:
                st.success(f"✅ {len(results)} stocks matched your criteria.")
                
                # Convert to dataframe
                df = pd.DataFrame(results)
                
                # Define color mapping functions
                def fa_score_color(val):
                    intensity = min(0.9, val/120)  # Cap intensity at 0.9
                    return f'background-color: rgba(144, 238, 144, {intensity})'  # Light green gradient
                
                def ta_score_color(val):
                    intensity = min(0.9, val/120)
                    return f'background-color: rgba(173, 216, 230, {intensity})'  # Light blue gradient
                
                def volatility_color(val):
                    volatility = float(str(val).replace('%',''))
                    intensity = min(0.9, (100 - volatility)/100)
                    return f'background-color: rgba(255, 182, 193, {intensity})'  # Light red gradient (reversed)
                
                def verdict_color(val):
                    if 'Undervalued' in val:
                        return 'background-color: #90EE90'  # Light green
                    elif 'Fair' in val:
                        return 'background-color: #ADD8E6'  # Light blue
                    elif 'Overvalued' in val:
                        return 'background-color: #FFCCCB'  # Light red
                    return ''
                
                # Apply styling
                styled_df = df.style.map(fa_score_color, subset=['FA Score']) \
                                .map(ta_score_color, subset=['TA Score']) \
                                .map(volatility_color, subset=['Volatility']) \
                                .map(verdict_color, subset=['Verdict']) \
                                .set_properties(**{'text-align': 'center'}) \
                                .format({'Volatility': '{:.2f}%'})
                
                # Display the styled dataframe
                st.write(styled_df.to_html(), unsafe_allow_html=True)
            else:
                st.warning("⚠️ No stocks matched the given filters.")

elif st.session_state.get("chat_mode") == "stock_leaderboard":
    if st.button("← Back to Main Menu"):
        st.session_state.chat_mode = None
        st.rerun()

    st.subheader("Stock Leaderboard")

    basis = st.radio("Select Analysis Period", ["Quarterly", "Annual"], 
                    horizontal=True, key="leaderboard_basis")
    
    if st.button("🔄 Refresh Data"):
        st.session_state.leaderboard_df = None
    
    if "leaderboard_df" not in st.session_state or st.button("Compute Scores"):
        with st.spinner(f"🔄 Computing {basis.lower()} scores..."):
            tickers = get_top_50_tickers("NSE")
            data = []
            
            for ticker in tickers:
                try:
                    ta = get_technical_analysis(ticker, basis=basis.lower())
                    fa = get_fundamental_analysis(ticker, basis=basis.lower())
                    sentiment = get_sentiment_analysis(ticker, basis=basis.lower())
                    vol = calculate_volatility(ticker)

                    if "error" not in ta and "error" not in fa and "error" not in sentiment:
                        final_score = round(
                            0.35 * fa["fa_score"] + 
                            0.35 * ta["ta_score"] + 
                            0.2 * sentiment["score"] * 10 + 
                            0.1 * (100 - vol), 2
                        )
                        
                        data.append({
                            "Ticker": ticker,
                            "FA Score": fa["fa_score"],
                            "TA Score": ta["ta_score"],
                            "Sentiment": sentiment["score"] * 10,
                            "Volatility": vol,
                            "Final Score": final_score
                        })
                except Exception:
                    continue
            
            st.session_state.leaderboard_df = pd.DataFrame(data)

    if "leaderboard_df" in st.session_state:
        df = st.session_state.leaderboard_df
        
        st.markdown("### Leaderboard Categories")
        col1, col2 = st.columns(2)
        col3, col4 = st.columns(2)
        
        if col1.button("Top 5 Strong Buys"):
            st.dataframe(df.sort_values("Final Score", ascending=False).head(5))
        if col2.button("Top 5 Undervalued"):
            st.dataframe(df.sort_values("FA Score", ascending=False).head(5))
        if col3.button("Top 5 Bullish"):
            st.dataframe(df.sort_values("TA Score", ascending=False).head(5))
        if col4.button("Top 5 Low Risk"):
            st.dataframe(df.sort_values("Volatility").head(5))

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


# Debug info (optional)
st.sidebar.markdown("### Debug Info")
st.sidebar.write("Current Mode:", st.session_state.get("chat_mode"))
st.sidebar.write("Show Buttons:", st.session_state.get("show_insight_buttons"))

