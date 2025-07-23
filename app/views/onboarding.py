import streamlit as st

# Onboarding and help logic for StockMatrix
def show_onboarding(st, user_prefs):
    st.title("Welcome to Stock Analyser!")
    st.markdown("""
    <div style='font-size:1.1rem;'>
    <b>Stock Analyser</b> is your all-in-one platform for screening, analyzing, and reporting on stocks across global markets.<br><br>
    <ul>
        <li>🧪 <b>Screener</b>: Find top stocks using advanced filters.</li>
        <li>🏆 <b>Leaderboard</b>: See the best performers by score.</li>
        <li>⚙️ <b>Run Analysis</b>: Deep-dive into fundamentals, technicals, sentiment, and risk.</li>
        <li>📄 <b>Report</b>: Generate and download detailed PDF reports.</li>
        <li>👀 <b>Watchlist</b>: Track your favorite stocks.</li>
    </ul>
    <br>
    <b>How to use:</b>
    <ol>
        <li>Choose a feature from the sidebar.</li>
        <li>Follow the on-screen instructions for each module.</li>
        <li>Customize your analysis and download reports as needed.</li>
    </ol>
    <br>
    <b>Tip:</b> Use the theme toggle in the sidebar to switch between light and dark mode.<br>
    </div>
    """, unsafe_allow_html=True)
    st.info("Get started by selecting a feature from the sidebar!")
