import streamlit as st
from backend.report_generator import generate_report
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
                basis = st.session_state.get('run_analysis_basis', 'quarterly')
                weights = st.session_state.get('final_weights', {})
                report_path = generate_report(
                    ticker=ticker,
                    basis=basis,
                    weights=weights,
                    fundamentals=st.session_state.get('fundamentals'),
                    technicals=st.session_state.get('technicals'),
                    perception=st.session_state.get('perception'),
                    risk=st.session_state.get('risk'),
                    final_score=st.session_state.get('final_score'),
                    verdict=st.session_state.get('final_verdict'),
                )
                if report_path and os.path.exists(report_path):
                    with open(report_path, "rb") as f:
                        st.download_button(
                            label="Download Report (PDF)",
                            data=f,
                            file_name=os.path.basename(report_path),
                            mime="application/pdf"
                        )
                else:
                    st.error("Failed to generate report file.")
            except Exception as e:
                st.error(f"Error generating report: {str(e)}")
