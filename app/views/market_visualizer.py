# app/views/market_visualizer.py
import streamlit as st
import pandas as pd
import numpy as np
import json
from backend.screener_engine import screen_stocks
from backend.market_selector import get_top_50_tickers

def show_market_visualizer(st, user_prefs):
    """
    Streamlit view for the 3D Market Visualization.
    """
    st.subheader("🌌 3D Market Visualizer")
    st.caption("Visualize market data in three dimensions. Run a screener to generate data.")

    exchange = st.selectbox(
        "Select Stock Exchange",
        ["NSE", "NYSE", "LSE", "HKEX", "TSE"],
        key="viz_exchange"
    )

    st.markdown("---")

    if st.button("🚀 Generate 3D Visualization", key="run_3d_viz_btn"):
        with st.spinner(f"Screening {exchange} to gather data for visualization..."):
            tickers = get_top_50_tickers(exchange)
            # We run a very open screen to get data for all stocks
            results = screen_stocks(
                tickers=tickers,
                min_upside=-100,
                min_ta=0,
                max_volatility=200
            )

            if not results:
                st.warning("No data could be gathered from the screener.")
                return

            # Convert to DataFrame for easier processing
            df = pd.DataFrame(results)
            
            # --- Data Preparation for 3D Plot ---
            # Ensure numeric types and handle potential errors
            df['TA Score'] = pd.to_numeric(df['TA Score'], errors='coerce')
            df['Volatility (%)'] = pd.to_numeric(df['Volatility (%)'], errors='coerce')
            # Use the helper from the screener to parse the percentage string
            df['Upside (%)'] = df['Upside (%)'].apply(lambda x: pd.to_numeric(str(x).replace('%',''), errors='coerce'))

            # Drop rows where essential data is missing
            df.dropna(subset=['TA Score', 'Volatility (%)', 'Upside (%)'], inplace=True)

            # --- FIX: Sanitize data by replacing NaN with None before JSON conversion ---
            df = df.replace({np.nan: None})

            # Normalize data for better visualization scaling (e.g., 0 to 1)
            df['x'] = (df['TA Score'] - df['TA Score'].min()) / (df['TA Score'].max() - df['TA Score'].min())
            df['y'] = (df['Volatility (%)'] - df['Volatility (%)'].min()) / (df['Volatility (%)'].max() - df['Volatility (%)'].min())
            df['z'] = (df['Upside (%)'] - df['Upside (%)'].min()) / (df['Upside (%)'].max() - df['Upside (%)'].min())
            
            # Select only the columns we need for the visualization
            plot_data = df[['Ticker', 'x', 'y', 'z']].to_dict(orient='records')
            
            st.session_state.plot_data_3d = plot_data
            st.success(f"Data for {len(plot_data)} stocks is ready for visualization.")

    if 'plot_data_3d' in st.session_state:
        plot_data = st.session_state.plot_data_3d
        
        # Read the HTML template
        try:
            with open("app/views/templates/3d_plot.html", "r") as f:
                html_template = f.read()
            
            # Inject the data into the HTML template
            html_with_data = html_template.replace("{{ PLOT_DATA }}", json.dumps(plot_data))
            
            st.markdown("### Interactive 3D Scatter Plot")
            st.caption("X-Axis: TA Score | Y-Axis: Volatility | Z-Axis: DCF Upside")
            st.components.v1.html(html_with_data, height=600)
        except FileNotFoundError:
            st.error("The 3d_plot.html template was not found. Please ensure it exists in app/views/templates/")
        except Exception as e:
            st.error(f"An error occurred while rendering the 3D plot: {e}")

