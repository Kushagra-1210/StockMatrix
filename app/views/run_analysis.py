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
    """Loads a CSS file and injects it into the Streamlit app."""
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"CSS file not found: {file_name}. Please ensure it exists at the correct path.")

def show_run_analysis(st, user_prefs):
    """Renders the 'Run Analysis' page with the professional dashboard UI."""
    # Load the specific CSS for this view
    load_view_css("app/views/css/run_analysis.css")

    st.markdown('<div class="run-analysis-container">', unsafe_allow_html=True)
    
    st.markdown("<h2>Run Analysis</h2>", unsafe_allow_html=True)
    st.markdown("<p class='page-subtitle'>Select your parameters to begin the analysis.</p>", unsafe_allow_html=True)

    # --- Main Layout: Two Columns ---
    main_cols = st.columns([2, 1], gap="large")

    # --- LEFT COLUMN: CONTROLS & CHART ---
    with main_cols[0]:
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
            if tickers:
                selected_ticker = st.selectbox("Stock", tickers, key="run_analysis_ticker")
            else:
                st.warning(f"No tickers found for {exchange}.")
                selected_ticker = None
        
        with control_cols[2]:
            industry = st.selectbox(
                "Industry",
                ['default', 'Energy', 'FMCG', 'Banking', 'Technology', 'Healthcare', 'Industrials', 'Consumer Cyclical'],
                key="run_analysis_industry"
            )

        # --- Re-integrated Customizer ---
        with st.expander("🎛️ Customize Scoring Model"):
            if 'user_weights' not in st.session_state:
                st.session_state.user_weights = {"fa": 35, "ta": 35, "sentiment": 20, "news": 10}
            
            weights = st.session_state.user_weights
            weights["fa"] = st.slider("Fundamental Analysis (%)", 0, 100, weights["fa"])
            weights["ta"] = st.slider("Technical Analysis (%)", 0, 100, weights["ta"])
            weights["sentiment"] = st.slider("Strategic Perception (%)", 0, 100, weights["sentiment"])
            weights["news"] = st.slider("News & Risk Safety (%)", 0, 100, weights["news"])
            
            total_weight = sum(weights.values())
            if total_weight != 100:
                st.error(f"Weights must add up to 100%. Current total: {total_weight}%")

        # --- Chart Section ---
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        
        info = {}
        history_df = pd.DataFrame()
        if selected_ticker:
            try:
                ticker_data = get_ticker_data(selected_ticker)
                info = ticker_data.get("info", {})
                history = ticker_data.get("history", {})
                if history:
                    history_df = pd.DataFrame(history)
                    if 'Date' in history_df.columns:
                        history_df['Date'] = pd.to_datetime(history_df['Date'])
                        history_df.set_index('Date', inplace=True)
            except Exception as e:
                st.error(f"Could not load data for {selected_ticker}: {e}")

        price = info.get('currentPrice', 0)
        prev_close = info.get('previousClose', 1)
        change_pct = ((price - prev_close) / prev_close) * 100 if prev_close and prev_close > 0 else 0
        change_class = "positive" if change_pct >= 0 else "negative"
        
        st.markdown(f"""
        <div class="chart-header">
            <h3>Stock Price Chart ({selected_ticker or 'N/A'})</h3>
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
                template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.1)'),
                height=320, margin=dict(l=0, r=0, t=10, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown('<div class="chart-placeholder"><p>Price chart will be displayed here.</p></div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # --- RIGHT COLUMN: ANALYSIS RESULTS ---
    with main_cols[1]:
        st.markdown("<h3>Analysis Results</h3>", unsafe_allow_html=True)
        
        is_disabled = (total_weight != 100) or (selected_ticker is None)

        if st.button("Run Full Analysis", use_container_width=True, disabled=is_disabled):
            with st.spinner(f"Running analysis for {selected_ticker}..."):
                st.session_state.technicals = ta_mod.analyze_technical_indicators(selected_ticker, industry=industry)
                st.session_state.fundamentals = fa_mod.analyze_fundamentals(selected_ticker)
                st.session_state.perception = sentiment_mod.analyze_perception(selected_ticker)
                st.session_state.risk = news_mod.fetch_news_risk(selected_ticker)

                tech = st.session_state.technicals
                fund = st.session_state.fundamentals
                perc = st.session_state.perception
                risk = st.session_state.risk

                if not any(d.get("error") for d in [tech, fund, perc, risk]):
                    weights = st.session_state.user_weights
                    fa_score = fund.get("Fundamental Score", 0)
                    ta_score = tech.get("ta_score", 0)
                    perception_score = perc.get("score", 0) * 10 
                    safety_score = 100 - risk.get("risk_score", 50)

                    final_score = (
                        (weights['fa'] / 100) * fa_score +
                        (weights['ta'] / 100) * ta_score +
                        (weights['sentiment'] / 100) * perception_score +
                        (weights['news'] / 100) * safety_score
                    )
                    st.session_state.final_score = final_score
                else:
                    st.session_state.final_score = None

        # --- Display Final Score ---
        if 'final_score' in st.session_state and st.session_state.final_score is not None:
             final_score = st.session_state.final_score
             if final_score >= 80: verdict, verdict_class = "Strong Buy", "positive"
             elif final_score >= 65: verdict, verdict_class = "Buy", "positive"
             elif final_score >= 45: verdict, verdict_class = "Hold", "neutral"
             else: verdict, verdict_class = "Sell", "negative"

             st.markdown(f"""
             <div class="final-score-container">
                <h4>Final Weighted Score</h4>
                <p class="final-score {verdict_class}">{final_score:.2f} / 100</p>
                <p class="final-verdict">Verdict: <span class="{verdict_class}">{verdict}</span></p>
             </div>
             """, unsafe_allow_html=True)

        # --- Helper to render breakdown dictionaries ---
        def render_breakdown(breakdown_dict):
            if not isinstance(breakdown_dict, dict): return "<p>No breakdown data available.</p>"
            html = "<dl class='breakdown-list'>"
            for key, value in breakdown_dict.items():
                html += f"<dt>{key}</dt><dd>{value}</dd>"
            html += "</dl>"
            return html

        # --- Display Individual Analysis Sections ---
        if 'technicals' in st.session_state and st.session_state.technicals:
            data = st.session_state.technicals
            score = data.get('ta_score', 0)
            verdict = data.get('verdict', 'N/A')
            verdict_class = "positive" if score >= 65 else "neutral" if score >= 45 else "negative"
            notes = data.get('notes', [])
            note_text = notes[0] if notes else "No specific notes generated."
            st.markdown(f"""
            <details class="group">
                <summary><h4>Technical Analysis</h4><p class="expander-subheader">Score: <span class="{verdict_class}">{score}/100</span> - Verdict: <span class="{verdict_class}">{verdict}</span></p></summary>
                <div class="expander-content">{render_breakdown(data.get('indicators', {}))} <p><strong>Notes:</strong> {note_text}</p></div>
            </details>""", unsafe_allow_html=True)

        if 'fundamentals' in st.session_state and st.session_state.fundamentals:
            data = st.session_state.fundamentals
            score = data.get('Fundamental Score', 0)
            verdict = data.get('Verdict', 'N/A')
            verdict_class = "positive" if score >= 65 else "neutral" if score >= 45 else "negative"
            notes = data.get('Notes', [])
            note_text = notes[0] if notes else "No specific notes generated."
            st.markdown(f"""
            <details class="group">
                <summary><h4>Fundamental Analysis</h4><p class="expander-subheader">Score: <span class="{verdict_class}">{score:.2f}/100</span> - Verdict: <span class="{verdict_class}">{verdict}</span></p></summary>
                <div class="expander-content">{render_breakdown(data.get('Breakdown', {}))} <p><strong>Notes:</strong> {note_text}</p></div>
            </details>""", unsafe_allow_html=True)

        if 'perception' in st.session_state and st.session_state.perception:
            data = st.session_state.perception
            score = data.get('score', 0) * 10
            verdict = data.get('verdict', 'N/A')
            verdict_class = "positive" if score >= 65 else "neutral" if score >= 45 else "negative"
            notes = data.get('management_notes', [])
            note_text = notes[0] if notes else "No specific notes generated."
            st.markdown(f"""
            <details class="group">
                <summary><h4>Perception Analysis</h4><p class="expander-subheader">Score: <span class="{verdict_class}">{score:.2f}/100</span> - Verdict: <span class="{verdict_class}">{verdict}</span></p></summary>
                <div class="expander-content"><p><strong>Notes:</strong> {note_text}</p></div>
            </details>""", unsafe_allow_html=True)
            
        if 'risk' in st.session_state and st.session_state.risk:
            data = st.session_state.risk
            safety_score = 100 - data.get('risk_score', 50)
            verdict = data.get('verdict', 'N/A')
            verdict_class = "positive" if safety_score >= 60 else "neutral" if safety_score >= 40 else "negative"
            notes = [data.get('note', "No specific notes generated.")]
            note_text = notes[0] if notes and notes[0] is not None else "No specific notes generated."
            st.markdown(f"""
            <details class="group">
                <summary><h4>Risk Analysis</h4><p class="expander-subheader">Safety Score: <span class="{verdict_class}">{safety_score:.2f}/100</span></p></summary>
                <div class="expander-content"><p><strong>Verdict:</strong> {verdict}</p><p><strong>Notes:</strong> {note_text}</p></div>
            </details>""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

