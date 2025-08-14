import streamlit as st
# --- THIS IS THE FIX ---
# Import the correctly named function for generating PDFs.
from backend.report_generator import generate_pdf_report
from datetime import datetime
import os

# Report Generator view logic for StockMatrix

def show_report(st, user_prefs):
    st.subheader("📄 Generate & Download Analysis Report")
    if "final_score" not in st.session_state or st.session_state.final_score is None:
        st.info("Please run an analysis first to generate a report.")
        return
    st.markdown("---")
    st.markdown(f"**Stock:** `{st.session_state.get('run_analysis_ticker', 'N/A')}`")
    st.markdown(f"**Date:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    st.markdown(f"**Final Score:** `{st.session_state.final_score}`")
    st.markdown(f"**Verdict:** `{st.session_state.final_verdict}`")
    st.markdown("---")
    if st.button("Generate PDF Report", key="generate_report_btn"):
        with st.spinner("Generating report..."):
            try:
                ticker = st.session_state.get('run_analysis_ticker', 'N/A')
                # --- THIS IS THE FIX ---
                # Call the correctly named function.
                report_path = generate_pdf_report(
                    stock_info={'ticker': ticker}, # Pass a dictionary for stock_info
                    technical_analysis=st.session_state.get('technicals', {}),
                    fundamental_analysis=st.session_state.get('fundamentals', {}),
                    sentiment_analysis=st.session_state.get('perception', {}),
                    news_risk=st.session_state.get('risk', {}),
                    final_score=st.session_state.get('final_score', 0),
                    final_verdict=st.session_state.get('final_verdict', 'N/A'),
                )
                if report_path:
                    st.download_button(
                        label="Download Report (PDF)",
                        data=report_path,
                        file_name=f"{ticker}_StockMatrix_Report.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.error("Failed to generate report file.")
            except Exception as e:
                st.error(f"Error generating report: {str(e)}")

