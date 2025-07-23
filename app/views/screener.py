# Screener view logic for StockMatrix

import pandas as pd
import time
from backend.market_selector import get_top_50_tickers
from backend.screener_engine import screen_stocks

def show_screener(st, user_prefs):
    st.subheader("📊 Screener Engine")
    basis = st.radio("Select Analysis Period", ["Quarterly", "Annual"], horizontal=True, key="screener_basis")
    st.markdown("**Choose an exchange**")
    exchange = st.selectbox("", ["NSE", "HKEX", "NYSE", "LSE", "TSE"], key="screener_exchange")
    col1, col2, col3 = st.columns(3)
    with col1:
        min_upside = col1.slider("Minimum DCF Upside (%)", -50, 200, 20)
    with col2:
        min_ta = st.slider("Minimum TA Score", 0, 100, 50)
    with col3:
        max_vol = st.slider("Volatility Threshold (Annualized %)", 0, 100, 50)

    # --- Real-time auto-refresh toggle ---
    auto_refresh = user_prefs.get("screener_auto_refresh", False)
    auto_refresh_toggle = st.checkbox("🔄 Auto-refresh every 30 seconds", value=auto_refresh, key="screener_auto_refresh")
    if auto_refresh_toggle != auto_refresh:
        user_prefs["screener_auto_refresh"] = auto_refresh_toggle
        from app.views.utils import save_user_prefs
        save_user_prefs(user_prefs)
        auto_refresh = auto_refresh_toggle

    if st.button("🔍 Find Stocks", key="screener_button") or auto_refresh:
        tickers = get_top_50_tickers(exchange)
        with st.spinner(f"Screening stocks on {exchange}..."):
            results = screen_stocks(
                tickers=tickers,
                min_upside=min_upside,
                min_ta=min_ta,
                max_volatility=max_vol
            )
            st.session_state.screener_results = results
        if auto_refresh:
            time.sleep(30)
            st.experimental_rerun()
    else:
        results = st.session_state.get("screener_results", [])

    if results:
        st.markdown(f"#### ✅ {len(results)} stocks matched your criteria.")
        df = pd.DataFrame(results)
        def highlight_cells(row):
            styles = ['' for _ in row]
            try:
                upside_val = float(str(row['Upside (%)']).replace('%', ''))
                if upside_val >= 50:
                    styles[1] = 'background-color: #d4edda; color: #155724;'
                elif upside_val >= 20:
                    styles[1] = 'background-color: #fff3cd; color: #856404;'
            except (ValueError, TypeError):
                pass
            try:
                ta_score = row['TA Score']
                if ta_score >= 70:
                    styles[2] = 'background-color: #d4edda; color: #155724;'
            except (ValueError, TypeError):
                pass
            try:
                vol_val = row['Volatility (%)']
                if vol_val > 75:
                    styles[3] = 'background-color: #f8d7da; color: #721c24;'
            except (ValueError, TypeError):
                pass
            return styles
        styled_df = df.style.apply(highlight_cells, axis=1).format({
            "Upside (%)": "{:.2f}%",
            "TA Score": "{:.2f}",
            "Volatility (%)": "{:.2f}%"
        })
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True,
            height=min(len(df) * 40 + 40, 600)
        )
