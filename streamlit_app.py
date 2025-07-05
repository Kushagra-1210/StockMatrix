# app/main.py
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

import logging
logging.basicConfig(level=logging.DEBUG)
st.set_option('client.showErrorDetails', True)

# 🔥 TEST: Is Streamlit rendering anything at all?
st.title("✅ StockMatrix is running")

from backend import technical_analysis as ta_mod
from backend import fundamental_analysis as fa_mod
from backend import sentiment_analysis as sentiment_mod
from backend import news_risk_analyzer as news_mod

# --- Cached Helper Functions ---
@st.cache_data(ttl=3600)
def get_technical_analysis(ticker, basis="annual"):
    return ta_mod.analyze_technical_indicators(ticker, basis=basis)

@st.cache_data(ttl=3600)
def get_fundamental_analysis(ticker, basis="annual"):
    return fa_mod.analyze_fundamentals(ticker, basis=basis)

@st.cache_data(ttl=1800)
def get_sentiment_analysis(ticker, basis = "annual"):
    return sentiment_mod.analyze_sentiment(ticker, basis = basis)

@st.cache_data(ttl=1800)
def get_news_risk_analysis(ticker,basis = "annual"):
    return news_mod.fetch_news_risk(ticker, basis = basis)

@st.cache_data(ttl=1800)
def get_yf_info(ticker):
    return yf.Ticker(ticker).info

@st.cache_data(ttl=1800)
def get_stock_history(ticker, period="6mo"):
    stock = yf.Ticker(ticker)
    return stock.history(period=period)


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

# --- Initial Chat Message ---
if not st.session_state.greeted:
    greeting_msg = (
        "👋 Hello! I am **StockMatrix - your AI Stock Assistant**.\n\n"
        "I analyze top 50 stocks from 5 major stock exchanges: **NSE, NYSE, LSE, HKEX, and TSE**.\n\n"
        "**What would you like to do today?**\n\n"
        "- Run Analysis(RA)\n"
        "- Generate a Report(GR)\n"
        "- Insight Generation(IG)\n\n"
        "Please type your choice below (RA / GR / IG)"
    )
    st.session_state.chat_history.append({"role": "assistant", "content": greeting_msg})
    st.session_state.greeted = True

# --- Display Chat History ---
for msg in st.session_state.chat_history:
    st.chat_message(msg["role"]).markdown(msg["content"])

# --- User Input ---
# --- User Input ---
user_input = st.chat_input("How can I help you today?", key="main_user_input")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    cmd = user_input.lower().strip().replace(" ", "")

    # Check for recognized commands
    if cmd in ["ra", "runanalysis"]:
        st.session_state.chat_mode = "run_analysis"
        response = "You selected Run Analysis. Please proceed."
        screener_data = None
        context = None

    elif cmd in ["gr", "generatereport", "report"]:
        st.session_state.chat_mode = "report"
        response = "You selected Report Generator. Please proceed."
        screener_data = None
        context = None

    elif cmd in ["ig", "insight", "insightgeneration"]:
        st.session_state.chat_mode = "insight_generation"
        response = "You selected **Insight Generation**. Please choose one of the options below:"
        screener_data = None
        context = None

    else:
        # For inputs other than commands, call chat handler
        response, screener_data, context = handle_chat_command(user_input)

        # If no chat mode set yet, clear it explicitly
        if "chat_mode" not in st.session_state:
            st.session_state.chat_mode = None

    # Show screener data if any
    if screener_data:
        st.dataframe(screener_data)

    # Show follow-up Q&A UI if context present (your existing code handles this)
    if context:
        # (Your follow-up chat UI here)
        pass

    # Show response if any and no follow-up context
    if response and not context:
        st.chat_message("assistant").markdown(response)

    # Show sorry message only if no valid command and no response
    if (
        (st.session_state.chat_mode is None or st.session_state.chat_mode == "") and
        (not response or response.strip() == "")
    ):
        st.chat_message("assistant").markdown(
        "⚠️ Sorry, I can only help with:\n\n"
        "- Run Analysis (RA)\n"
        "- Generate Report (GR)\n"
        "- Insight Generation (IG)\n"
        "Please type one of these to continue."
    )


# --- Module Handling ---
if "chat_mode" in st.session_state:

    if st.session_state.chat_mode == "run_analysis":
        st.subheader("🧪 Run Analysis Module")

        st.subheader("1. Select Stock Exchange")
        exchange = st.selectbox("Choose an exchange:", options=["NSE", "HKEX", "NYSE", "LSE", "TSE"], key="run_analysis_exchange")

        if exchange:
            tickers = get_top_50_tickers(exchange)
            selected_ticker = st.selectbox("2. Choose a Stock", tickers, key="run_analysis_ticker")

            col1, col2 = st.columns(2)
            with col1:
                auto_refresh = st.checkbox("🔄 Auto-refresh every 30 seconds", key="auto_refresh_checkbox")
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
                        fig.update_layout(title="Price Trend (6 Months)", xaxis_title="Date", yaxis_title=f"Price ({currency})")
                        st.plotly_chart(fig)

                        if auto_refresh:
                            time.sleep(30)
                            st.experimental_rerun()

                    except Exception as e:
                        st.error(f"Error fetching stock data: {str(e)}")

            with col2:
                analysis_type = st.radio("Select Analysis Type", ["Technical", "Fundamental", "Both"], key="analysis_type")
                basis = st.radio("Select Data Basis", ["Quarterly", "Annual"], horizontal=True, key="data_basis")

                if st.button("Run Analysis", key="run_analysis_btn"):
                    with st.spinner("🔍 Running analysis... Please wait."):
                        refresh_tech = st.checkbox("🔄 Refresh Technical Analysis", key="refresh_technical")
                        refresh_fund = st.checkbox("🔄 Refresh Fundamental Analysis", key="refresh_fundamental")
                        refresh_sent = st.checkbox("🔄 Refresh Sentiment Analysis", key="refresh_sentiment")
                        refresh_news = st.checkbox("🔄 Refresh News & Risk Analysis", key="refresh_news")
 
                        if refresh_tech:
                            ta = ta_mod.analyze_technical_indicators(selected_ticker, basis=basis)
                        else:
                            ta = get_technical_analysis(selected_ticker, basis=basis)
                        if refresh_fund:
                            fa = fa_mod.analyze_fundamentals(selected_ticker, basis=basis)
                        else:
                            fa = get_fundamental_analysis(selected_ticker, basis=basis)
                        if refresh_sent:
                            sentiment = sentiment_mod.analyze_sentiment(selected_ticker, basis=basis)
                        else:
                            sentiment = get_sentiment_analysis(selected_ticker, basis=basis)
                        if refresh_news:
                            news_risk = news_mod.fetch_news_risk(selected_ticker, basis=basis)
                        else:
                            news_risk = get_news_risk_analysis(selected_ticker, basis=basis)
                            
                        if analysis_type == "Technical":
                            st.subheader("🧪 Technical Analysis Report")
                            try:
                                result = get_technical_analysis(selected_ticker, basis=basis)
                                if "error" in result:
                                    st.error(result["error"])
                                else:
                                    st.markdown(f"""
                                    - **Current Price**: {result['current_price']}  
                                    - **RSI (14)**: {result['rsi']}  
                                    - **SMA-20**: {result['sma_20']}  
                                    - **EMA-20**: {result['ema_20']}  
                                    - **TA Score**: {result['ta_score']} / 100  
                                    - **Verdict**: **{result['verdict']}**
                                    """)
                                    st.markdown('<p style="font-size: 10px; color: grey;">Source: Yahoo Finance (historical data)</p>', unsafe_allow_html=True)
                                    if "ta_breakdown" in result:
                                        st.markdown("##### 🔍 Technical Score Breakdown")
                                        for factor, value in result["ta_breakdown"].items():
                                            st.markdown(f"- **{factor}**: {value}")
                            except Exception as e:
                                st.error(f"TA failed: {str(e)}")

                        elif analysis_type == "Fundamental":
                            st.subheader("📊 Fundamental Analysis Report")
                            try:
                                result = get_fundamental_analysis(selected_ticker, basis=basis)
                                if "error" in result:
                                    st.error(result["error"])
                                else:
                                    fcf = result.get("fcf", "N/A")
                                    fcf_disp = f"{fcf:,}" if isinstance(fcf, (int, float)) else "N/A"
                                    st.markdown(f"""
                                    - **Market Cap**: {result['market_cap']:,} ({result['size']})  
                                    - **EPS**: {result['eps']}  
                                    - **ROE**: {result['roe']}%  
                                    - **PE Ratio**: {result['pe_ratio']}  
                                    - **Debt-to-Equity**: {result['de_ratio']}  
                                    - **Free Cash Flow**: {fcf_disp}
                                    - **Data As of**: {result['fiscal_date']}  
                                    - **FA Score**: {result['fa_score']} / 100  
                                    - **Verdict**: **{result['verdict']}**
                                    """)
                                    st.markdown('<p style="font-size: 10px; color: grey;">Source: Yahoo Finance (via yfinance)</p>', unsafe_allow_html=True)
                                    if "fa_breakdown" in result:
                                        st.markdown("##### 🔍 Fundamental Score Breakdown")
                                        for factor, value in result["fa_breakdown"].items():
                                            st.markdown(f"- **{factor}**: {value}")
                                    
                            except Exception as e:
                                st.error(f"FA failed: {str(e)}")


                        elif analysis_type == "Both":
                            ta = get_technical_analysis(selected_ticker, basis=basis)
                            fa = get_fundamental_analysis(selected_ticker, basis=basis)
                            sentiment = get_sentiment_analysis(selected_ticker, basis=basis)
                            news_risk = get_news_risk_analysis(selected_ticker, basis=basis)

                            if any("error" in mod for mod in [ta, fa, sentiment, news_risk]):
                                st.error("One or more modules failed.")
                            else:
                                st.subheader("🧪 Technical Analysis")
                                st.markdown(f"""
                                - **Current Price**: {ta['current_price']}  
                                - **RSI (14)**: {ta['rsi']}  
                                - **SMA-20**: {ta['sma_20']}  
                                - **EMA-20**: {ta['ema_20']}  
                                - **TA Score**: {ta['ta_score']} / 100  
                                - **Verdict**: **{ta['verdict']}**
                                """)
                                st.markdown('<p style="font-size: 10px; color: grey;">Source: Yahoo Finance (historical data)</p>', unsafe_allow_html=True)
                                if "ta_breakdown" in ta:
                                    st.markdown("##### 🔍 Technical Score Breakdown")
                                    for factor, value in ta["ta_breakdown"].items():
                                        st.markdown(f"- **{factor}**: {value}")

                                st.subheader("📊 Fundamental Analysis")
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
                                - **FA Score**: {fa['fa_score']} / 100  
                                - **Verdict**: **{fa['verdict']}**
                                """)
                                st.markdown('<p style="font-size: 10px; color: grey;">Source: Yahoo Finance (via yfinance)</p>', unsafe_allow_html=True)
                                if "fa_breakdown" in fa:
                                    st.markdown("##### 🔍 Fundamental Score Breakdown")
                                    for factor, value in fa["fa_breakdown"].items():
                                        st.markdown(f"- **{factor}**: {value}")

                                st.subheader("💬 Sentiment Analysis")
                                st.markdown(f"""
                                - **Sentiment Score**: {sentiment['score']} / 10  
                                - **Label**: {sentiment['label']}
                                """)
                                st.markdown('<p style="font-size: 10px; color: grey;">Source: Google News RSS</p>', unsafe_allow_html=True)

                                for news in sentiment["headlines"]:
                                    st.markdown(f"- [{news['title']}]({news['link']})")

                                if "news" in news_risk:
                                    st.subheader("🛡️ News & Geopolitical Risk")
                                    st.markdown(f"- **Risk Score**: {news_risk['risk_score']} / 100")
                                    st.markdown(f"- **Verdict**: **{news_risk['verdict']}**")
                                    st.markdown("Recent Headlines:")
                                    st.markdown('<p style="font-size: 10px; color: grey;">Source: Simulated via Google News RSS</p>', unsafe_allow_html=True)
                                    for item in news_risk["news"]:
                                        st.markdown(f"- 📰 {item['title']} — **{item['risk']} Risk**")

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

                                st.subheader("📌 Final Investment Decision")
                                st.markdown(f"""
                                - **Combined Score**: {final_score} / 100  
                                - **Verdict**: **{final_verdict}**
                                """)

    elif st.session_state.chat_mode == "insight_generation":
        st.subheader("🔎 Insight Generation")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("📊 Screener Engine"):
                st.session_state.chat_mode = "screener"
                st.rerun()

        with col2:
            if st.button("📈 Stock Leaderboard"):
                st.session_state.chat_mode = "stock_leaderboard"
                st.rerun()
                
    elif st.session_state.chat_mode == "report":
        st.subheader("📄 Report Generator")
        report_mod = importlib.import_module("backend.report_generator")
        
        exchange = st.selectbox("Select Exchange", ["NSE", "HKEX", "NYSE", "LSE", "TSE"], key="report_exchange")
        if exchange:
            tickers = get_top_50_tickers(exchange)
            selected_ticker = st.selectbox("Choose a Stock", tickers, key="report_ticker")

            if st.button("Generate Report", key="generate_report_btn"):
                with st.spinner("Fetching and analyzing data..."):
                    basis = st.radio("Select Data Basis", ["Quarterly", "Annual"], horizontal=True, key="report_basis")
                    ta = importlib.import_module("backend.technical_analysis").analyze_technical_indicators(selected_ticker)
                    fa = importlib.import_module("backend.fundamental_analysis").analyze_fundamentals(selected_ticker)
                    sentiment = importlib.import_module("backend.sentiment_analysis").analyze_sentiment(selected_ticker)
                    news_risk = importlib.import_module("backend.news_risk_analyzer").fetch_news_risk(selected_ticker)

                    if any("error" in mod for mod in [ta, fa, sentiment, news_risk]):
                        st.error("Error in analysis. Cannot generate report.")
                    else:
                        stock = yf.Ticker(selected_ticker)
                        info = stock.info
                        stock_info = {
                            "ticker": selected_ticker,
                            "name": info.get("shortName", ""),
                            "price": info.get("currentPrice", "N/A"),
                            "date": datetime.now().strftime("%Y-%m-%d"),
                        }

                        final_score = round(
                            0.35 * fa["fa_score"] +
                            0.35 * ta["ta_score"] +
                            0.2 * sentiment["score"] * 10 +
                            0.1 * news_risk["risk_score"], 2
                        )
                        final_verdict = (
                            "Strong Buy" if final_score >= 80 else
                            "Buy" if final_score >= 65 else
                            "Hold" if final_score >= 50 else "Sell"
                        )

                        pdf = report_mod.generate_pdf_report(stock_info, ta, fa, sentiment, final_score, final_verdict, news_risk)
                        csv = report_mod.generate_csv_report([{
                            **ta, **fa,
                            "sentiment_score": sentiment.get("score", "N/A"),
                            "sentiment_label": sentiment.get("label", "N/A"),
                            "news_risk_score": news_risk.get("risk_score", "N/A"),
                            "news_risk_verdict": news_risk.get("verdict", "N/A"),
                            "final_score": final_score,
                            "final_verdict": final_verdict
                        }])

                        st.success("Report generated! Download below:")
                        st.download_button("Download PDF", data=pdf, file_name=f"{selected_ticker}_report.pdf", mime="application/pdf")
                        st.download_button("Download CSV", data=csv, file_name=f"{selected_ticker}_report.csv", mime="text/csv")

    elif st.session_state.chat_mode == "screener":
        st.subheader("📊 Screener Engine")

        ta_mod = importlib.import_module("backend.technical_analysis")
        fa_mod = importlib.import_module("backend.fundamental_analysis")
        from backend.market_selector import get_top_50_tickers

        exchange = st.selectbox("Select Exchange", ["NSE", "HKEX", "NYSE", "LSE", "TSE"], key="screener_exchange")
        min_fa = st.slider("Minimum Fundamental Score", 0, 100, 50, key="screener_fa")
        min_ta = st.slider("Minimum Technical Score", 0, 100, 50, key="screener_ta")
        max_vol = st.slider("Maximum Volatility (%)", 0, 100, 50, key="screener_vol")

        if st.button("Run Screener", key="run_screener_btn"):
            import concurrent.futures
            with st.spinner("⏳ Screening stocks... Please wait."):
                tickers = get_top_50_tickers(exchange)

                def analyze_stock(ticker):
                    try:
                        fa = fa_mod.analyze_fundamentals(ticker)
                        ta = ta_mod.analyze_technical_indicators(ticker)
                        vol = calculate_volatility(ticker)

                        if "error" in fa or "error" in ta:
                            return None

                        if fa["fa_score"] >= min_fa and ta["ta_score"] >= min_ta and vol <= max_vol:
                            return {
                                "Ticker": ticker,
                                "FA Score": fa["fa_score"],
                                "TA Score": ta["ta_score"],
                                "Volatility": vol,
                                "Final Verdict": fa["verdict"]
                            }
                    except Exception:
                        return None
                    return None

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    results = list(executor.map(analyze_stock, tickers))

                filtered = [r for r in results if r is not None]

                if filtered:
                    df = pd.DataFrame(filtered)
                    st.success(f"{len(df)} stocks matched your criteria.")
                    st.dataframe(df)
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button("Download CSV", csv, "screener_results.csv", "text/csv")
                else:
                    st.warning("No stocks matched the criteria.")
                    
    elif st.session_state.chat_mode == "stock_leaderboard":
        st.subheader("Stock Leaderboard")
        from backend.market_selector import get_top_50_tickers
        from backend.technical_analysis import analyze_technical_indicators
        from backend.fundamental_analysis import analyze_fundamentals
        from backend.sentiment_analysis import analyze_sentiment
        from backend.screener_engine import calculate_volatility

        leaderboard_type = st.session_state.get("leaderboard_type", None)

        categories = {
            "Top 5 Strong Buys": lambda df: df.sort_values("Final Score", ascending=False).head(5),
            "Top 5 Undervalued Stocks": lambda df: df.sort_values("PE Ratio").head(5),
            "Top 5 Bullish Momentum": lambda df: df.sort_values("TA Score", ascending=False).head(5),
            "Top 5 Low Risk": lambda df: df.sort_values("Volatility").head(5),
            "Top 5 High Volatility": lambda df: df.sort_values("Volatility", ascending=False).head(5),
            "Top 5 Negative Sentiment": lambda df: df.sort_values("Sentiment Score").head(5),
            "Top 5 Midcap Opportunities": lambda df: df[df["Market Cap"] < 10_000_000_000].sort_values("Final Score", ascending=False).head(5)
        }

        def fetch_all_scores():
            tickers = get_top_50_tickers("NSE")  # Can extend to user-selectable exchange
            data = []
            for ticker in tickers:
                try:
                    ta = analyze_technical_indicators(ticker)
                    fa = analyze_fundamentals(ticker)
                    sentiment = analyze_sentiment(ticker)
                    vol = calculate_volatility(ticker)

                    if "error" in ta or "error" in fa or "error" in sentiment:
                        continue

                    final_score = round(0.35 * fa["fa_score"] + 0.35 * ta["ta_score"] + 0.2 * sentiment["score"] * 10 + 0.1 * (100 - vol), 2)

                    data.append({
                        "Ticker": ticker,
                        "TA Score": ta["ta_score"],
                        "FA Score": fa["fa_score"],
                        "Sentiment Score": sentiment["score"] * 10,
                        "PE Ratio": fa["pe_ratio"],
                        "Market Cap": fa["market_cap"],
                        "Volatility": vol,
                        "Final Score": final_score
                    })
                except Exception:
                    continue
            return pd.DataFrame(data)

        if "leaderboard_df" not in st.session_state:
            with st.spinner("🔄 Computing leaderboard scores... Please wait."):
                st.session_state.leaderboard_df = fetch_all_scores()

        col1, col2 = st.columns(2)
        col3, col4 = st.columns(2)
        col5, col6 = st.columns(2)
        col7 = st.columns(1)[0]

        for label, col in zip(categories.keys(), [col1, col2, col3, col4, col5, col6, col7]):
            if col.button(label):
                st.session_state.leaderboard_type = label
                st.rerun()

        if leaderboard_type and "leaderboard_df" in st.session_state:
            df = st.session_state.leaderboard_df.copy()
            top_df = categories[leaderboard_type](df)
            st.markdown(f"### 🏆 {leaderboard_type}")
            st.dataframe(top_df)

            st.markdown("⬇️ Explore other leaderboard categories:")
            st.session_state.leaderboard_type = None  # Reset for re-loop behavior