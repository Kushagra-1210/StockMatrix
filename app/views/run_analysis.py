import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.market_selector import get_top_50_tickers
from backend.data_fetcher import get_ticker_data
from datetime import datetime
import plotly.graph_objs as go
import pandas as pd
import streamlit as st

# Run Analysis view logic for StockMatrix

def show_run_analysis(st, user_prefs):
    st.subheader("⚙️ Run Analysis Module")
    st.markdown('<div class="ra-selectbox-wrapper">', unsafe_allow_html=True)
    st.markdown("Select Data Basis")
    basis = st.radio(
        label="Select basis",
        options=["Quarterly", "Annual"],
        horizontal=True,
        key="run_analysis_basis",
        label_visibility="collapsed"
    )
    st.markdown("1. Choose an Exchange")
    exchange = st.selectbox(
    label="Select exchange",  # Give it a real label
    options=["NSE", "HKEX", "NYSE", "LSE", "TSE"],
    key="run_analysis_exchange",
    label_visibility="collapsed"  # This hides the label visually but keeps it accessible
    )

    tickers = get_top_50_tickers(exchange)
    if "last_exchange" not in st.session_state or st.session_state.last_exchange != exchange:
        st.session_state["run_analysis_ticker"] = tickers[0] if tickers else None
        st.session_state.last_exchange = exchange

    st.markdown("2. Choose a Stock", unsafe_allow_html=True)
    selected_ticker = st.selectbox("Choose a stock", tickers, key="run_analysis_ticker")

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("3. Select the Stock's Industry", unsafe_allow_html=True)
    industry = st.selectbox(
        "Industry",
        options=['default', 'Energy', 'FMCG', 'Banking', 'Technology', 'Healthcare', 'Industrials', 'Consumer Cyclical'],
        key="run_analysis_industry",
        help="Select the industry to use appropriate benchmarks for technical analysis."
    )

    st.markdown("---")
    if 'analysis_expander_open' not in st.session_state:
        st.session_state.analysis_expander_open = True
    def open_expander():
        st.session_state.analysis_expander_open = True
    def close_expander():
        st.session_state.analysis_expander_open = False
    with st.expander("🎛️ Customize Scoring Model", expanded=st.session_state.analysis_expander_open):
        st.markdown("Adjust the weights for each analysis category. **They must add up to 100%.**")
        if 'user_weights' not in st.session_state:
            st.session_state.user_weights = {"fa": 35, "ta": 35, "sentiment": 20, "news": 10}
        weights = st.session_state.user_weights
        weights["fa"] = st.slider("Fundamental Analysis (%)", 0, 100, weights["fa"], key="analysis_fa_slider", on_change=open_expander)
        weights["ta"] = st.slider("Technical Analysis (%)", 0, 100, weights["ta"], key="analysis_ta_slider", on_change=open_expander)
        weights["sentiment"] = st.slider("Strategic Perception Analysis (%)", 0, 100, weights["sentiment"], key="analysis_sentiment_slider", on_change=open_expander)
        weights["news"] = st.slider("News & Risk Analysis (%)", 0, 100, weights["news"], key="analysis_news_slider", on_change=open_expander)
        st.button("Close Customization Panel", on_click=close_expander)
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        auto_refresh = st.checkbox("🔄 Auto-refresh every 30 seconds", key="auto_refresh_checkbox")
        if st.button("Stock Price", key="run_analysis_price_btn") or (st.session_state.get("auto_refresh_checkbox") and st.session_state.get("auto_refreshing")):
            st.session_state.auto_refreshing = auto_refresh
            try:
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
                chart_type = st.selectbox(
                    "Select Chart Type",
                    ["Line", "Candlestick", "Bar"],
                    key="run_analysis_chart_type"
                )
                show_moving_avg = st.checkbox("Show Moving Average (20d)", value=False, key="run_analysis_ma")
                show_volume = st.checkbox("Show Volume", value=False, key="run_analysis_vol")
                if history and "Close" in history and history["Close"]:
                    min_len = len(history["Close"])
                    
                    df_data = {"Close": history["Close"]}
                    
                    if "Open" in history and len(history["Open"]) == min_len:
                        df_data["Open"] = history["Open"]
                    if "High" in history and len(history["High"]) == min_len:
                        df_data["High"] = history["High"]
                    if "Low" in history and len(history["Low"]) == min_len:
                        df_data["Low"] = history["Low"]
                    if "Volume" in history and len(history["Volume"]) == min_len:
                        df_data["Volume"] = history["Volume"]

                    df = pd.DataFrame(df_data)
                    
                    if "Date" in history and len(history["Date"]) == min_len:
                        df.index = pd.to_datetime(history["Date"])
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
                    if show_moving_avg:
                        df["MA20"] = df["Close"].rolling(window=20).mean()
                        fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA 20d", line=dict(dash="dash")))
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
                    st.components.v1.html(
                        """
                        <meta http-equiv=\"refresh\" content=\"30\">""",
                        height=0,
                    )
            except Exception as e:
                st.error(f"Error fetching stock data: {str(e)}")
    with col2:
        total_weight = sum(st.session_state.user_weights.values())
        is_disabled = (total_weight != 100)
        if st.button("Run Analysis", key="run_analysis_btn", disabled=is_disabled):
            from app.views.utils import reset_analysis_data
            reset_analysis_data()
            with st.spinner(f"🔍 Running {basis.lower()} analysis for {selected_ticker}..."):
                try:
                    from backend import technical_analysis as ta_mod, fundamental_analysis as fa_mod, sentiment_analysis as sentiment_mod, news_risk_analyzer as news_mod
                    
                    st.session_state.technicals = ta_mod.analyze_technical_indicators(
                        ticker = selected_ticker, 
                        industry=industry, 
                        basis=basis.lower()
                        )

                    st.session_state.fundamentals = fa_mod.analyze_fundamentals(selected_ticker, basis=basis.lower())
                    st.session_state.perception = sentiment_mod.analyze_perception(selected_ticker)
                    st.session_state.risk = news_mod.fetch_news_risk(selected_ticker, basis=basis.lower())
                    if "error" not in st.session_state.fundamentals and "error" not in st.session_state.technicals:
                        user_weights = st.session_state.user_weights
                        
                        fundamental_score = st.session_state.fundamentals.get("Fundamental Score", 0)
                        technical_score = st.session_state.technicals.get("ta_score", 0)
                        perception_score = st.session_state.perception.get("strategic_perception_score", 0) * 5
                        risk_score = st.session_state.risk.get("risk_score", 50)

                        fa_weight = user_weights.get("fa", 0) / 100
                        ta_weight = user_weights.get("ta", 0) / 100
                        sentiment_weight = user_weights.get("sentiment", 0) / 100
                        news_weight = user_weights.get("news", 0) / 100
                        
                        final_score = round(
                            (fa_weight * fundamental_score) +
                            (ta_weight * technical_score) +
                            (sentiment_weight * perception_score) +
                            (news_weight * risk_score),
                            2
                        )

                        final_verdict = ("Strong Buy" if final_score >= 80 else "Buy" if final_score >= 65 else "Hold" if final_score >= 50 else "Sell")
                        st.session_state.final_score = final_score
                        st.session_state.final_verdict = final_verdict
                        st.session_state.final_weights = user_weights
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
        st.divider()
        weights = st.session_state.user_weights
        if st.session_state.get("technicals") and weights.get("ta", 0) > 0:
            with st.expander("🧪 Technical Analysis", expanded=True):
                data = st.session_state.technicals
                if "error" in data:
                    st.error(f"Analysis Failed: {data['error']}")
                else:
                    st.metric(label="Technical Score", value=f"{data.get('ta_score', 0)}/100")
                    st.write(f"**Verdict:** `{data.get('verdict', 'N/A')}`")
                    indicators = data.get('indicators', {})
                    if indicators:
                        st.markdown("---")
                        st.markdown("#### Key Technical Indicators:")
                        if isinstance(indicators, dict):
                            # Create a DataFrame for better layout
                            df_indicators = pd.DataFrame(list(indicators.items()), columns=['Indicator', 'Value'])
                            st.table(df_indicators)
                        else:
                            st.write(indicators)
                    
                    # --- THIS IS THE NEWLY ADDED NOTE ---
                    if data.get("methodology_note"):
                        st.caption(f"📝 {data['methodology_note']}")
                    # --- END OF NEW CODE ---

                    notes = data.get('notes', [])
                    if notes:
                        st.markdown("**Technical Analysis Notes:**")
                        for note in notes:
                            st.caption(f"📝 {note}")
                            
        if st.session_state.get("fundamentals") and weights.get("fa", 0) > 0:
            with st.expander("📊 Fundamental Analysis", expanded=True):
                # ... (rest of the fundamental analysis display logic)
                data = st.session_state.fundamentals
                final_score = data.get("Fundamental Score")
                verdict = data.get("Verdict")
                if final_score is not None:
                    st.metric(label="Combined Fundamental Score", value=f"{final_score:.2f}/100")
                    st.subheader(f"Verdict: {verdict}")
                st.markdown("---")
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
                notes = data.get("Notes", [])
                if notes:
                    st.markdown("#### Analysis Notes:")
                    for note in notes:
                        st.caption(f"📝 {note}")

        if st.session_state.get("perception") and weights.get("sentiment", 0) > 0:
            with st.expander("🔎 Strategic Perception Analysis", expanded=True):
                # ... (rest of the perception analysis display logic)
                data = st.session_state.perception
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

        if st.session_state.get("risk") and weights.get("news", 0) > 0:
            with st.expander("🛡️ News & Geopolitical Risk", expanded=True):
                # ... (rest of the news/risk display logic)
                data = st.session_state.risk
                if "error" in data:
                    st.error(f"Analysis Failed: {data['error']}")
                else:
                    st.metric(label="Risk Score", value=f"{data.get('risk_score', 0):.1f}/100")
                    st.markdown(f"**Verdict:** `{data.get('verdict', 'N/A')}`")
                    st.markdown("**Recent Risk Headlines:**")
                    note = data.get("note")
                    if note:
                        st.info(note)
                    headlines = data.get("headlines", [])
                    if headlines:
                        if isinstance(headlines[0], dict):
                            for h in headlines[:3]:
                                st.markdown(f"- {h.get('headline', str(h))}")
                        else:
                            for h in headlines[:3]:
                                st.markdown(f"- {h}")
                    else:
                        st.info("No headlines found.")

        if "final_score" in st.session_state and st.session_state.final_score is not None:
            st.markdown("### 📌 Final Investment Decision")
            weights = st.session_state.final_weights
            st.caption(f"Calculated with weights: FA {weights['fa']}%, TA {weights['ta']}%, Strategic Perception {weights['sentiment']}%, News {weights['news']}%")
            st.markdown(f"- **Combined Score**: {st.session_state.final_score}/100\n- **Verdict**: **{st.session_state.final_verdict}**")
