# Leaderboard view logic for StockMatrix

import pandas as pd
from backend.leaderboard_engine import get_leaderboard

def show_leaderboard(st, user_prefs):
    st.subheader("🏆 Stock Leaderboard")
    with st.expander("🎛️ Customize Leaderboard Scoring Model"):
        st.markdown("Adjust the weights for each analysis category. **They must add up to 100%.**")
        if 'user_weights' not in st.session_state:
            st.session_state.user_weights = {"fa": 35, "ta": 35, "sentiment": 20, "news": 10}
        weights = st.session_state.user_weights
        weights["fa"] = st.slider("Fundamental Analysis (%)", 0, 100, weights["fa"], key="leaderboard_fa_slider")
        weights["ta"] = st.slider("Technical Analysis (%)", 0, 100, weights["ta"], key="leaderboard_ta_slider")
        weights["sentiment"] = st.slider("Strategic Perception Analysis (%)", 0, 100, weights["sentiment"], key="leaderboard_sentiment_slider")
        weights["news"] = st.slider("News & Risk Analysis (%)", 0, 100, weights["news"], key="leaderboard_news_slider")
    st.markdown("---")
    basis = st.radio("Select Analysis Period", ["Quarterly", "Annual"], horizontal=True, key="leaderboard_basis")
    exchange = st.selectbox("Select Stock Exchange", ["NSE", "NYSE", "TSE", "LSE", "HKEX"], key="leaderboard_exchange")
    total_weight_leaderboard = sum(st.session_state.user_weights.values())
    is_leaderboard_disabled = (total_weight_leaderboard != 100)
    if st.button("🔄 Compute/Refresh Data", disabled=is_leaderboard_disabled):
        with st.spinner(f"Computing leaderboard for {exchange}..."):
            df = get_leaderboard(exchange)
            if df is not None and not df.empty:
                st.session_state.leaderboard_df = df
            else:
                st.session_state.leaderboard_df = None
                st.success("Leaderboard data refreshed successfully!")
    if 'leaderboard_df' in st.session_state and st.session_state.leaderboard_df is not None:
        st.markdown("###  Leaderboard Results")
        df = st.session_state.leaderboard_df.copy()
        col_map = {
            "fa": ["FA Score", "Fundamental Score"],
            "ta": ["TA Score", "Technical Score"],
            "sentiment": ["Perception Score", "Strategic Perception Score", "Sentiment Score"],
            "news": ["News Score", "Risk Score", "risk_score", "news_score"]
        }
        def find_col(possibles):
            for c in possibles:
                if c in df.columns:
                    return c
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
        if "Safety Score" in show_cols:
            show_cols.remove("Safety Score")
        st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
