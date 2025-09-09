# app/views/backtesting.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from backend.backtesting_engine import BacktestingEngine
from backend.market_selector import get_top_50_tickers
import logging

logger = logging.getLogger(__name__)

def show_backtesting(st, user_prefs):
    """
    Streamlit view for the Backtesting Engine.
    """
    st.subheader("🚀 Backtesting Engine")
    st.caption("Test the StockMatrix strategy against historical market data.")

    # --- Configuration ---
    col1, col2 = st.columns(2)
    with col1:
        exchange = st.selectbox(
            "Select Stock Exchange",
            ["NSE", "NYSE", "LSE", "HKEX", "TSE"],
            key="backtest_exchange"
        )
    with col2:
        # Simple benchmark mapping
        benchmark_map = {
            "NSE": "^NSEI", # NIFTY 50
            "NYSE": "^GSPC", # S&P 500
            "LSE": "^FTSE", # FTSE 100
            "HKEX": "^HSI", # Hang Seng Index
            "TSE": "^N225"  # Nikkei 225
        }
        benchmark = st.text_input("Benchmark Ticker", value=benchmark_map.get(exchange, "^GSPC"))

    start_date = st.date_input("Start Date", value=pd.to_datetime("2022-01-01"))
    end_date = st.date_input("End Date", value=pd.to_datetime("2023-12-31"))

    st.markdown("---")

    if st.button("📈 Run Backtest", key="run_backtest_btn"):
        if not exchange or not benchmark:
            st.warning("Please select an exchange and a benchmark.")
            return

        tickers = get_top_50_tickers(exchange)
        
        with st.spinner(f"Running backtest for {exchange}... This may take several minutes."):
            try:
                engine = BacktestingEngine(
                    tickers=tickers,
                    benchmark_ticker=benchmark,
                    start_date=str(start_date),
                    end_date=str(end_date)
                )
                results = engine.run_simulation()
                st.session_state.backtest_results = results
                st.success("Backtest simulation completed!")

            except Exception as e:
                st.error(f"An error occurred during the backtest: {e}")
                logger.error("Backtest failed", exc_info=True)
                return

    # --- Display Results ---
    if "backtest_results" in st.session_state and st.session_state.backtest_results:
        results = st.session_state.backtest_results
        performance_df = results.get("performance_df")
        metrics = results.get("metrics", {})

        if performance_df is None or performance_df.empty or not metrics:
            st.warning("Backtest ran but did not produce valid results. Please check the logs.")
            return

        st.markdown("### Performance Comparison")

        # --- Key Metrics ---
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Strategy Total Return", f"{metrics.get('total_return_strategy_pct', 0):.2f}%")
        m_col2.metric("Benchmark Total Return", f"{metrics.get('total_return_benchmark_pct', 0):.2f}%")
        m_col3.metric("Alpha", f"{metrics.get('alpha_pct', 0):.2f}%")
        
        # --- Performance Chart ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=performance_df.index,
            y=performance_df['Strategy'],
            name='StockMatrix Strategy',
            line=dict(color='royalblue', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=performance_df.index,
            y=performance_df['Benchmark'],
            name=f"{metrics.get('benchmark_ticker', 'Benchmark')}",
            line=dict(color='grey', width=2, dash='dash')
        ))
        fig.update_layout(
            title_text='Portfolio Growth (Starting Value: $100,000)',
            xaxis_title="Date",
            yaxis_title="Portfolio Value ($)",
            legend_title="Portfolio"
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- Detailed Metrics Table ---
        st.markdown("### Key Performance Indicators")
        
        data = {
            'Metric': ['CAGR', 'Sharpe Ratio'],
            'Strategy': [f"{metrics.get('cagr_strategy_pct', 0):.2f}%", f"{metrics.get('sharpe_strategy', 0):.2f}"],
            'Benchmark': [f"{metrics.get('cagr_benchmark_pct', 0):.2f}%", f"{metrics.get('sharpe_benchmark', 0):.2f}"]
        }
        metrics_df = pd.DataFrame(data).set_index('Metric')
        st.table(metrics_df)

