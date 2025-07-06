from fpdf import FPDF
import io
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio
import yfinance as yf
from datetime import datetime

def generate_pdf_report(
    stock_info: dict,
    technical: dict,
    fundamental: dict,
    sentiment: dict,
    final_score: float,
    final_verdict: str,
    news_risk: dict = None
) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Stock Analysis Report: {stock_info.get('ticker', '')}", 0, 1, "C")

    # Stock Chart
    try:
        stock = yf.Ticker(stock_info["ticker"])
        hist = stock.history(period="6mo")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Close Price"))
        fig.update_layout(title="Price Trend (6 Months)", xaxis_title="Date", yaxis_title="Price")
        img_bytes = pio.to_image(fig, format="png", width=700, height=400)
        img_path = "temp_chart.png"
        with open(img_path, "wb") as f:
            f.write(img_bytes)
        pdf.image(img_path, x=10, y=30, w=pdf.w - 20)
        pdf.ln(95)
    except Exception as e:
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 10, f"(Chart not available: {str(e)})", 0, 1)

    # Summary
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Summary", 0, 1)
    pdf.set_font("Arial", "", 12)
    # In the "Summary" section of the PDF:
    pdf.multi_cell(0, 8, f"""
    Ticker: {stock_info.get('ticker', '')}
    Name: {stock_info.get('name', 'N/A')}
    Analysis Period: {stock_info.get('basis', 'N/A')}  # Changed from technical.get()
    Current Price: {stock_info.get('price', 'N/A')}
    """)

    # Technical
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Technical Analysis", 0, 1)
    pdf.set_font("Arial", "", 12)
    for key in ["rsi", "sma_20", "ema_20", "ta_score", "verdict"]:
        pdf.cell(0, 8, f"{key.replace('_', ' ').title()}: {technical.get(key, 'N/A')}", 0, 1)

    # Fundamental
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Fundamental Analysis", 0, 1)
    pdf.set_font("Arial", "", 12)
    for key in ["market_cap", "eps", "roe", "pe_ratio", "de_ratio", "fa_score", "verdict"]:
        pdf.cell(0, 8, f"{key.replace('_', ' ').title()}: {fundamental.get(key, 'N/A')}", 0, 1)

    # Sentiment
    # 💬 Sentiment Analysis
    if sentiment:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Sentiment Analysis", 0, 1)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 8, f"Sentiment Score: {sentiment.get('score', 'N/A')} / 10", 0, 1)
        pdf.cell(0, 8, f"Label: {sentiment.get('label', 'N/A')}", 0, 1)

        if sentiment.get("headlines"):
            pdf.set_font("Arial", "I", 11)
            pdf.cell(0, 10, "Sample Headlines:", 0, 1)
            pdf.set_font("Arial", "", 10)
            for item in sentiment["headlines"]:
                if pdf.get_y() > 260:
                    pdf.add_page()
                label = item.get("label", "")
                title = item.get("title", "")
                headline = f"{title} ({label})"
                pdf.multi_cell(0, 6, f"- {headline}")

    # News Risk
    if news_risk:
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "News & Geopolitical Risk", 0, 1)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 8, f"Risk Score: {news_risk.get('risk_score', 'N/A')} / 100", 0, 1)
        pdf.cell(0, 8, f"Verdict: {news_risk.get('verdict', 'N/A')}", 0, 1)

        if news_risk.get("news"):
            pdf.set_font("Arial", "I", 11)
            pdf.cell(0, 10, "Sample Headlines:", 0, 1)
            pdf.set_font("Arial", "", 10)
            for item in news_risk["news"]:
                if pdf.get_y() > 260:
                    pdf.add_page()
                title = item.get("title", "")
                headline = f"- {title}"
                pdf.multi_cell(0, 6, headline)

    # Final Score
    pdf.ln(10)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Final Investment Decision", 0, 1)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Combined Score: {final_score} / 100", 0, 1)
    pdf.cell(0, 8, f"Verdict: {final_verdict}", 0, 1)

    return pdf.output(dest='S').encode('latin-1')

def generate_csv_report(data: list) -> bytes:
    df = pd.DataFrame(data)
    return df.to_csv(index=False).encode('utf-8')
