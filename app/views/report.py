import streamlit as st
from backend.report_generator import generate_pdf_report
from datetime import datetime
import os
from backend.market_selector import get_top_50_tickers
from backend import technical_analysis as ta_mod
from backend import fundamental_analysis as fa_mod
from backend import sentiment_analysis as sentiment_mod
from backend import news_risk_analyzer as news_mod
from backend.data_provider import DataProvider # Import the DataProvider

# Report Generator view logic for StockMatrix

def show_report(st, user_prefs):
    st.subheader("📄 Generate & Download Analysis Report")
    
    st.markdown("1. Choose an Exchange")
    exchange = st.selectbox(
        label="Select exchange",
        options=["NSE", "HKEX", "NYSE", "LSE", "TSE"],
        key="report_exchange",
        label_visibility="collapsed"
    )

    tickers = get_top_50_tickers(exchange)
    
    st.markdown("2. Choose a Stock")
    selected_ticker = st.selectbox(
        "Choose a stock", 
        tickers, 
        key="report_ticker"
    )
    
    st.markdown("---")

    if st.button("Generate PDF Report", key="generate_report_btn"):
        if not selected_ticker:
            st.warning("Please select a stock to generate a report.")
            return

        with st.spinner(f"Running analysis and generating report for {selected_ticker}..."):
            try:
                # --- NEW: Fetch historical data for the chart ---
                provider = DataProvider(selected_ticker)
                historical_data = provider.get_history()

                technicals = ta_mod.analyze_technical_indicators(selected_ticker)
                fundamentals = fa_mod.analyze_fundamentals(selected_ticker)
                perception = sentiment_mod.analyze_perception(selected_ticker)
                risk = news_mod.fetch_news_risk(selected_ticker)

                fa_score = fundamentals.get("Fundamental Score", 50)
                ta_score = technicals.get("ta_score", 50)
                perception_score = perception.get("strategic_perception_score", 10) * 5
                risk_score = 100 - risk.get("risk_score", 50)

                final_score = (0.35 * fa_score) + (0.35 * ta_score) + (0.20 * perception_score) + (0.10 * risk_score)
                final_verdict = ("Strong Buy" if final_score >= 80 else "Buy" if final_score >= 65 else "Hold" if final_score >= 50 else "Sell")

                pdf_data = generate_pdf_report(
                    stock_info={'ticker': selected_ticker, 'name': perception.get('company_name', '')},
                    technical_analysis=technicals,
                    fundamental_analysis=fundamentals,
                    sentiment_analysis=perception,
                    news_risk=risk,
                    final_score=final_score,
                    final_verdict=final_verdict,
                    historical_data=historical_data # Pass the data to the function
                )

                if pdf_data:
                    st.download_button(
                        label="Download Report (PDF)",
                        data=pdf_data,
                        file_name=f"{selected_ticker}_StockMatrix_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.error("Failed to generate report file.")
            except Exception as e:
                st.error(f"Error generating report: {str(e)}")

