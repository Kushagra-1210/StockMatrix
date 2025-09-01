import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from backend.market_selector import get_top_50_tickers
from backend.data_fetcher import get_ticker_data
from backend import technical_analysis as ta_mod
from backend import fundamental_analysis as fa_mod
from backend import sentiment_analysis as sentiment_mod
from backend import news_risk_analyzer as news_mod

def load_view_css(file_name):
    """Loads a CSS file and injects it into the Streamlit app."""
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"CSS file not found: {file_name}")

def render_breakdown(breakdown_dict):
    """Helper function to render a dictionary of metrics into a 2-column HTML list."""
    if not isinstance(breakdown_dict, dict):
        return "<p>No detailed breakdown available.</p>"
    html = "<dl class='breakdown-list'>"
    for key, value in breakdown_dict.items():
        # Sanitize and format keys
        display_key = str(key).replace('_', ' ').title()
        html += f"<dt>{display_key}</dt><dd>{value}</dd>"
    html += "</dl>"
    return html

def show_run_analysis(st, user_prefs):
    """Renders the 'Run Analysis' page with interactive cards."""
    load_view_css("app/views/css/run_analysis.css")

    st.markdown("<h2>Run Analysis</h2>", unsafe_allow_html=True)
    st.markdown("<p class='page-subtitle'>Select your parameters to begin the analysis.</p>", unsafe_allow_html=True)

    # --- CONTROLS ---
    control_cols = st.columns(3)
    with control_cols[0]:
        exchange = st.selectbox("Exchange", ["NSE", "HKEX", "NYSE", "LSE", "TSE"], key="ra_exchange")
    tickers = get_top_50_tickers(exchange)
    with control_cols[1]:
        selected_ticker = st.selectbox("Stock", tickers, key="ra_stock") if tickers else None
    with control_cols[2]:
        industry = st.selectbox("Industry", ['default', 'Energy', 'FMCG', 'Banking', 'Technology', 'Healthcare'], key="ra_industry")

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

    # --- CHART ---
    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    info = get_ticker_data(selected_ticker).get("info", {}) if selected_ticker else {}
    history = get_ticker_data(selected_ticker).get("history", {}) if selected_ticker else {}
    history_df = pd.DataFrame(history)
    if 'Date' in history_df.columns:
        history_df['Date'] = pd.to_datetime(history_df['Date'])
        history_df = history_df.set_index('Date')

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

    if not history_df.empty:
        fig = go.Figure(data=go.Scatter(x=history_df.index, y=history_df['Close'], mode='lines', line=dict(color='#7B61FF')))
        fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=320, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown('<div class="chart-placeholder"><p>Price chart will be displayed here.</p></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    # --- RUN ANALYSIS & RESULTS ---
    if st.button("Run Full Analysis", use_container_width=True, disabled=(total_weight != 100 or not selected_ticker)):
        with st.spinner(f"Running full analysis for {selected_ticker}..."):
            st.session_state.technicals = ta_mod.analyze_technical_indicators(selected_ticker, industry=industry)
            st.session_state.fundamentals = fa_mod.analyze_fundamentals(selected_ticker)
            st.session_state.perception = sentiment_mod.analyze_perception(selected_ticker)
            st.session_state.risk = news_risk_analyzer.fetch_news_risk(selected_ticker)

            tech = st.session_state.technicals
            fund = st.session_state.fundamentals
            perc = st.session_state.perception
            risk = st.session_state.risk

            if not any(isinstance(d, dict) and d.get("error") for d in [tech, fund, perc, risk]):
                weights = st.session_state.user_weights
                fa_score = fund.get("Fundamental Score", 0)
                ta_score = tech.get("ta_score", 0)
                perception_score = perc.get("score", 0) * 10
                safety_score = 100 - risk.get("risk_score", 50)
                final_score = ((weights['fa']/100) * fa_score + (weights['ta']/100) * ta_score +
                               (weights['sentiment']/100) * perception_score + (weights['news']/100) * safety_score)
                st.session_state.final_score = final_score
            else:
                st.session_state.final_score = None

    # --- RENDER RESULTS ---
    if 'final_score' in st.session_state and st.session_state.final_score is not None:
        final_score = st.session_state.final_score
        if final_score >= 80: verdict, v_class = "Strong Buy", "positive"
        elif final_score >= 65: verdict, v_class = "Buy", "positive"
        elif final_score >= 45: verdict, v_class = "Hold", "neutral"
        else: verdict, v_class = "Sell", "negative"

        st.markdown(f"""
        <div class="final-score-card">
            <h4>Final Weighted Score</h4>
            <p class="final-score {v_class}">{final_score:.2f} / 100</p>
            <p>Verdict: <span class="final-verdict {v_class}">{verdict}</span></p>
        </div>
        """, unsafe_allow_html=True)

        # --- Analysis Cards Grid ---
        grid = st.columns(2)
        with grid[0]:
            tech = st.session_state.get('technicals', {})
            if tech.get("error"):
                st.error(f"Technical Analysis Failed: {tech.get('error')}")
            else:
                score = tech.get('ta_score', 0)
                verdict = tech.get('verdict', 'N/A')
                v_class = "positive" if score >= 65 else "neutral" if score >= 45 else "negative"
                notes = tech.get('notes', [])
                note_text = notes[0] if notes else "No specific notes generated."
                st.markdown(f"""
                <details class="analysis-card-details">
                    <summary>
                        <h5>Technical Analysis</h5>
                        <span class="score {v_class}">Score: {score}/100</span>
                        <span class="verdict">Verdict: {verdict}</span>
                    </summary>
                    <div class="card-content">
                        {render_breakdown(tech.get('indicators', {}))}
                        <p><strong>Notes:</strong> {note_text}</p>
                    </div>
                </details>
                """, unsafe_allow_html=True)

            fund = st.session_state.get('fundamentals', {})
            if fund.get("error"):
                 st.error(f"Fundamental Analysis Failed: {fund.get('error')}")
            else:
                score = fund.get('Fundamental Score', 0)
                verdict = fund.get('Verdict', 'N/A')
                v_class = "positive" if score >= 65 else "neutral" if score >= 45 else "negative"
                notes = fund.get('Notes', [])
                note_text = notes[0] if notes else "No specific notes generated."
                st.markdown(f"""
                <details class="analysis-card-details">
                    <summary>
                        <h5>Fundamental Analysis</h5>
                        <span class="score {v_class}">Score: {score:.2f}/100</span>
                        <span class="verdict">Verdict: {verdict}</span>
                    </summary>
                     <div class="card-content">
                        {render_breakdown(fund.get('Breakdown', {}))}
                        <p><strong>Notes:</strong> {note_text}</p>
                    </div>
                </details>
                """, unsafe_allow_html=True)

        with grid[1]:
            perc = st.session_state.get('perception', {})
            if perc.get("error"):
                st.error(f"Perception Analysis Failed: {perc.get('error')}")
            else:
                score = perc.get('score', 0) * 10
                verdict = perc.get('verdict', 'N/A')
                v_class = "positive" if score >= 65 else "neutral" if score >= 45 else "negative"
                notes = perc.get('management_notes', [])
                note_text = notes[0] if notes else "No specific notes generated."
                st.markdown(f"""
                <details class="analysis-card-details">
                    <summary>
                        <h5>Perception Analysis</h5>
                        <span class="score {v_class}">Score: {score:.2f}/100</span>
                        <span class="verdict">Verdict: {verdict.split(':')[0]}</span>
                    </summary>
                    <div class="card-content">
                        {render_breakdown(perc)}
                        <p><strong>Notes:</strong> {note_text}</p>
                    </div>
                </details>
                """, unsafe_allow_html=True)

            risk = st.session_state.get('risk', {})
            if risk.get("error"):
                 st.error(f"Risk Analysis Failed: {risk.get('error')}")
            else:
                score = 100 - risk.get('risk_score', 50)
                verdict = risk.get('verdict', 'N/A')
                v_class = "positive" if score >= 60 else "neutral" if score >= 40 else "negative"
                note = risk.get('note', "No specific notes generated.")
                headlines = risk.get('headlines', [])
                st.markdown(f"""
                <details class="analysis-card-details">
                    <summary>
                        <h5>Risk Analysis (Safety Score)</h5>
                        <span class="score {v_class}">Score: {score:.2f}/100</span>
                        <span class="verdict">Verdict: {verdict.split(':')[0]}</span>
                    </summary>
                    <div class="card-content">
                        <p><strong>Notes:</strong> {note}</p>
                    </div>
                </details>
                """, unsafe_allow_html=True)

