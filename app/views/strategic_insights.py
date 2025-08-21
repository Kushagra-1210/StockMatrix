# app/views/strategic_insights.py
import streamlit as st
import pandas as pd
from backend import strategic_insights as si
from backend.market_selector import get_top_50_tickers

def show_strategic_insights(st, user_prefs):
    st.header("📈 Strategic Insights")
    st.markdown("Analyze stocks against proven investment strategies.")

    # --- Mode Selection ---
    analysis_mode = st.radio(
        "Choose Analysis Mode",
        ("Check a Single Stock", "Screen the Market"),
        horizontal=True,
        key="insights_mode"
    )
    st.markdown("---")

    # --- SINGLE STOCK PROFILE CHECKER ---
    if analysis_mode == "Check a Single Stock":
        st.subheader("Strategic Profile for a Single Stock")
        
        exchange = st.selectbox(
            "1. Choose an Exchange",
            options=["NSE", "HKEX", "NYSE", "LSE", "TSE"],
            key="insights_exchange"
        )
        tickers = get_top_50_tickers(exchange)
        selected_ticker = st.selectbox(
            "2. Choose a Stock",
            tickers,
            key="insights_ticker"
        )

        if st.button("Generate Strategic Profile", key="generate_insights_btn"):
            if not selected_ticker:
                st.warning("Please select a stock.")
                return

            with st.spinner(f"Analyzing {selected_ticker} against strategic profiles..."):
                # This new backend function does all the work
                matched_strategies, notes = si.check_single_stock_strategies(selected_ticker)
                st.session_state.insights_results = {
                    "ticker": selected_ticker,
                    "matches": matched_strategies,
                    "notes": notes
                }
        
        # Display results for single stock check
        if 'insights_results' in st.session_state and st.session_state.insights_results:
            results = st.session_state.insights_results
            st.markdown("---")
            st.subheader(f"Strategic Profile for: {results['ticker']}")

            if results['matches'] and "Analysis failed" not in results['matches'][0]:
                st.markdown("This stock aligns with the following profiles:")
                for match in results['matches']:
                    st.success(match)
                st.markdown("---")
                st.markdown("#### Analyst Notes:")
                for note in results['notes']:
                    st.markdown(f"- {note}")
            else:
                st.info(results['matches'][0]) # Show the info/error message

    # --- MARKET SCREENING MODE ---
    elif analysis_mode == "Screen the Market":
        st.subheader("Screen Market for a Specific Strategy")
        
        # Load data if available from the main screener
        stock_data = st.session_state.get("stock_data_df")
        news_verdicts = st.session_state.get("news_verdicts", {})
        
        if stock_data is None or not isinstance(stock_data, pd.DataFrame) or stock_data.empty:
            st.info("To screen the market, please run the main 'Screener' from the chat window first to generate a dataset.")
            return

        strategy_map = {
            "GARP Strategy (Growth at a Reasonable Price)": si.run_garp_strategy,
            "Fallen Angels (Quality + Value)": si.run_fallen_angels,
            "Value Trap Detector (Risk-Averse Value)": lambda df: si.run_value_trap_filter(df, news_verdicts),
            "Momentum + Quality Combo": si.run_momentum_quality_combo,
            "Low Volatility Anomaly": lambda df: si.run_low_volatility_anomaly(df, news_verdicts)
        }

        selected_strategy = st.selectbox("Choose a Strategy to Apply", list(strategy_map.keys()))

        if st.button(f"Run {selected_strategy}", key="run_strategy_screen_btn"):
            strategy_func = strategy_map[selected_strategy]
            with st.spinner("Applying strategy filter..."):
                result_df = strategy_func(stock_data)
                st.session_state.strategy_screen_results = result_df

        if 'strategy_screen_results' in st.session_state:
            result_df = st.session_state.strategy_screen_results
            st.markdown(f"### Results: {len(result_df)} stocks matched")
            st.dataframe(result_df)

