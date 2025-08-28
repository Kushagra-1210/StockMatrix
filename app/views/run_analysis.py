import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from backend.market_selector import get_top_50_tickers
from backend.data_fetcher import get_ticker_data
from datetime import datetime
from backend import technical_analysis as ta_mod
from backend import fundamental_analysis as fa_mod
from backend import sentiment_analysis as sentiment_mod
from backend import news_risk_analyzer as news_mod

# --- Helper function to load the new CSS ---
def load_view_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"CSS file not found: {file_name}. Please ensure it exists.")

def show_run_analysis(st, user_prefs):
    # Load the specific CSS for this view
    load_view_css("app/views/css/run_analysis.css")

    st.markdown('<div class="run-analysis-container">', unsafe_allow_html=True)
    
    st.markdown("<h2>Run Analysis</h2>", unsafe_allow_html=True)
    st.markdown("<p>Select your parameters to begin the analysis.</p>", unsafe_allow_html=True)

    # --- Main Layout ---
    main_cols = st.columns([2, 1], gap="large")

    with main_cols[0]: # Left column for controls and chart
        # --- Input Controls ---
        control_cols = st.columns(3)
        with control_cols[0]:
            exchange = st.selectbox(
                "Exchange",
                ["NSE", "HKEX", "NYSE", "LSE", "TSE"],
                key="run_analysis_exchange"
            )
        tickers = get_top_50_tickers(exchange)
        with control_cols[1]:
            selected_ticker = st.selectbox("Stock", tickers, key="run_analysis_ticker")
        with control_cols[2]:
            industry = st.selectbox(
                "Industry",
                ['default', 'Energy', 'FMCG', 'Banking', 'Technology', 'Healthcare', 'Industrials', 'Consumer Cyclical'],
                key="run_analysis_industry"
            )

        # --- Chart Section ---
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        
        info = {}
        history_df = pd.DataFrame()
        try:
            ticker_data = get_ticker_data(selected_ticker)
            info = ticker_data.get("info", {})
            history = ticker_data.get("history", {})
            if history:
                history_df = pd.DataFrame(history)
                history_df['Date'] = pd.to_datetime(history_df['Date'])
                history_df.set_index('Date', inplace=True)
        except Exception as e:
            st.error(f"Could not load data for {selected_ticker}: {e}")

        price = info.get('currentPrice', 0)
        prev_close = info.get('previousClose', 1)
        change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0
        change_class = "positive" if change_pct >= 0 else "negative"
        
        st.markdown(f"""
        <div class="chart-header">
            <h3>Stock Price Chart ({selected_ticker})</h3>
            <div class="price-display">
                <span class="current-price">${price:,.2f}</span>
                <span class="price-change-{change_class}">{change_pct:+.2f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.caption("Last 12 Months")

        if not history_df.empty:
            fig = go.Figure(data=go.Scatter(x=history_df.index, y=history_df['Close'], mode='lines', line=dict(color='#7B61FF')))
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.1)'),
                height=320,
                margin=dict(l=0, r=0, t=10, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Price chart data not available.")

        st.markdown('</div>', unsafe_allow_html=True)


    with main_cols[1]: # Right column for analysis results
        st.markdown("<h3>Analysis Results</h3>", unsafe_allow_html=True)
        
        if st.button("Run Full Analysis", use_container_width=True):
            with st.spinner(f"Running analysis for {selected_ticker}..."):
                st.session_state.technicals = ta_mod.analyze_technical_indicators(selected_ticker, industry=industry)
                st.session_state.fundamentals = fa_mod.analyze_fundamentals(selected_ticker)
                st.session_state.perception = sentiment_mod.analyze_perception(selected_ticker)
                st.session_state.risk = news_mod.fetch_news_risk(selected_ticker)

        # --- Display Results ---
        if 'technicals' in st.session_state and st.session_state.technicals:
            data = st.session_state.technicals
            score = data.get('ta_score', 0)
            verdict = data.get('verdict', 'N/A')
            verdict_class = "positive" if score >= 65 else "neutral" if score >= 45 else "negative"
            st.markdown(f"""
            <details class="group">
                <summary>
                    <h4>Technical Analysis</h4>
                    <p class="expander-subheader">Score: <span class="{verdict_class}">{score}/100</span> - Verdict: <span class="{verdict_class}">{verdict}</span></p>
                </summary>
                <div class="expander-content">
                    <p><strong>Notes:</strong> {data.get('notes', ['No notes available.'])[0]}</p>
                </div>
            </details>
            """, unsafe_allow_html=True)

        if 'fundamentals' in st.session_state and st.session_state.fundamentals:
            data = st.session_state.fundamentals
            score = data.get('Fundamental Score', 0)
            verdict = data.get('Verdict', 'N/A')
            verdict_class = "positive" if score >= 65 else "neutral" if score >= 45 else "negative"
            st.markdown(f"""
            <details class="group">
                <summary>
                    <h4>Fundamental Analysis</h4>
                    <p class="expander-subheader">Score: <span class="{verdict_class}">{score:.2f}/100</span> - Verdict: <span class="{verdict_class}">{verdict}</span></p>
                </summary>
                <div class="expander-content">
                    <p><strong>Notes:</strong> {data.get('Notes', ['No notes available.'])[0]}</p>
                </div>
            </details>
            """, unsafe_allow_html=True)

        if 'perception' in st.session_state and st.session_state.perception:
            data = st.session_state.perception
            score = data.get('score', 0) * 10
            verdict = data.get('verdict', 'N/A')
            verdict_class = "positive" if score >= 65 else "neutral" if score >= 45 else "negative"
            st.markdown(f"""
            <details class="group">
                <summary>
                    <h4>Perception Analysis</h4>
                    <p class="expander-subheader">Score: <span class="{verdict_class}">{score:.2f}/100</span> - Verdict: <span class="{verdict_class}">{verdict}</span></p>
                </summary>
                <div class="expander-content">
                    <p><strong>Notes:</strong> {data.get('management_notes', ['No notes available.'])[0]}</p>
                </div>
            </details>
            """, unsafe_allow_html=True)
            
        if 'risk' in st.session_state and st.session_state.risk:
            data = st.session_state.risk
            score = 100 - data.get('risk_score', 50) # Inverted score for display
            verdict = data.get('verdict', 'N/A')
            verdict_class = "positive" if score >= 60 else "neutral" if score >= 40 else "negative"
            st.markdown(f"""
            <details class="group">
                <summary>
                    <h4>Risk Analysis</h4>
                    <p class="expander-subheader">Safety Score: <span class="{verdict_class}">{score:.2f}/100</span> - Verdict: <span class="{verdict_class}">{verdict}</span></p>
                </summary>
                <div class="expander-content">
                    <p><strong>Headlines:</strong> {len(data.get('headlines', []))} risk headlines considered.</p>
                </div>
            </details>
            """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
