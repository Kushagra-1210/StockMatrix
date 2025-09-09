# backend/backtest_report_generator.py
import io
import pandas as pd
from fpdf import FPDF
import plotly.graph_objects as go
import logging

logger = logging.getLogger(__name__)

def generate_backtest_report(metrics: dict, performance_df: pd.DataFrame) -> bytes:
    """
    Generates a one-page PDF summarizing the backtest results.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- Header ---
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 10, "StockMatrix Backtest Performance Report", 0, 1, 'C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, f"Period: {metrics.get('start_date', 'N/A')} to {metrics.get('end_date', 'N/A')}", 0, 1, 'C')
    pdf.ln(10)

    # --- Key Metrics Summary ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Overall Performance", 0, 1, 'L')

    # Create a table for the main metrics
    pdf.set_font("Arial", '', 10)
    col_width = pdf.w / 4.5
    line_height = pdf.font_size * 2
    
    # Headers
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(col_width, line_height, 'Metric', 1, 0, 'C')
    pdf.cell(col_width, line_height, 'Strategy', 1, 0, 'C')
    pdf.cell(col_width, line_height, 'Benchmark', 1, 0, 'C')
    pdf.cell(col_width, line_height, 'Alpha', 1, 1, 'C')

    # Data Rows
    pdf.set_font("Arial", '', 10)
    pdf.cell(col_width, line_height, 'Total Return', 1, 0, 'C')
    pdf.cell(col_width, line_height, f"{metrics.get('total_return_strategy_pct', 0):.2f}%", 1, 0, 'C')
    pdf.cell(col_width, line_height, f"{metrics.get('total_return_benchmark_pct', 0):.2f}%", 1, 0, 'C')
    pdf.cell(col_width, line_height, f"{metrics.get('alpha_pct', 0):.2f}%", 1, 1, 'C')

    pdf.cell(col_width, line_height, 'CAGR', 1, 0, 'C')
    pdf.cell(col_width, line_height, f"{metrics.get('cagr_strategy_pct', 0):.2f}%", 1, 0, 'C')
    pdf.cell(col_width, line_height, f"{metrics.get('cagr_benchmark_pct', 0):.2f}%", 1, 1, 'C')

    pdf.cell(col_width, line_height, 'Sharpe Ratio', 1, 0, 'C')
    pdf.cell(col_width, line_height, f"{metrics.get('sharpe_strategy', 0):.2f}", 1, 0, 'C')
    pdf.cell(col_width, line_height, f"{metrics.get('sharpe_benchmark', 0):.2f}", 1, 1, 'C')
    pdf.ln(10)

    # --- Performance Chart ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Portfolio Growth Over Time", 0, 1, 'L')

    try:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=performance_df.index, y=performance_df['Strategy'], name='StockMatrix Strategy'))
        fig.add_trace(go.Scatter(x=performance_df.index, y=performance_df['Benchmark'], name=f"{metrics.get('benchmark_ticker', 'Benchmark')}"))
        fig.update_layout(
            title="Portfolio Value (Initial $100,000)",
            xaxis_title="Date", yaxis_title="Value ($)",
            template="plotly_white",
            height=400, width=600,
            legend=dict(x=0.01, y=0.99)
        )

        img_bytes = fig.to_image(format="png", scale=2)
        
        with io.BytesIO(img_bytes) as img_file:
            # Center the image
            img_width = 180 # mm
            x_pos = (pdf.w - img_width) / 2
            pdf.image(img_file, x=x_pos, w=img_width)
    except Exception as e:
        logger.error(f"Failed to generate chart for PDF report: {e}")
        pdf.set_font("Arial", 'I', 10)
        pdf.set_text_color(255, 0, 0)
        pdf.cell(0, 10, "Chart could not be generated.", 0, 1, 'C')
        pdf.set_text_color(0, 0, 0)

    # --- Footer ---
    pdf.set_y(-15)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 10, f'Page {pdf.page_no()}', 0, 0, 'C')
    pdf.cell(0, 10, 'Disclaimer: For informational purposes only. Past performance is not indicative of future results.', 0, 0, 'R')

    return pdf.output(dest='S').encode('latin-1')

