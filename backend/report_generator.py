import io
from fpdf import FPDF
import plotly.io as pio

# --- Helper Function ---

def sanitize(text):
    """
    Sanitizes text to be compatible with FPDF by replacing special characters.
    This prevents errors when writing text that contains characters FPDF
    interprets as formatting, such as parentheses or backslashes.
    """
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- Main Report Generation Function ---

def generate_pdf_report(
    ticker,
    fig, # The Plotly figure object for the stock chart
    info,
    news_sentiment,
    risk_analysis,
    technical_analysis,
    fundamental_analysis,
    dcf_analysis,
    m_score,
    piotroski_score
):
    """
    Generates a comprehensive PDF report for a given stock ticker.

    Args:
        ticker (str): The stock ticker symbol.
        fig (go.Figure): A Plotly figure object for the stock price chart.
        info (dict): General company information.
        news_sentiment (dict): News sentiment analysis results.
        risk_analysis (dict): News-based risk analysis results.
        technical_analysis (dict): Technical analysis scores.
        fundamental_analysis (dict): Fundamental analysis scores.
        dcf_analysis (dict): Discounted Cash Flow analysis results.
        m_score (str): Beneish M-Score result.
        piotroski_score (str): Piotroski F-Score result.

    Returns:
        bytes: The generated PDF report as a byte string, ready for download.
    """
    pdf = FPDF()
    pdf.add_page()

    # --- Header ---
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 10, f'Stock Analysis Report: {ticker.upper()}', 0, 1, 'C')
    pdf.set_font("Arial", '', 10)
    company_name = info.get('longName', 'N/A')
    pdf.cell(0, 10, sanitize(company_name), 0, 1, 'C')
    pdf.ln(5)

    # --- Stock Chart ---
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, 'Stock Price Chart', 0, 1, 'L')

    # Generate the chart image as a bytes object in memory
    chart_image_bytes = pio.to_image(fig, format="png", width=800, height=300)

    # Create an in-memory binary stream from the bytes object
    in_memory_chart = io.BytesIO(chart_image_bytes)

    # Add the image from the in-memory stream to the PDF
    # The width (w) is set to the page width minus margins
    pdf.image(in_memory_chart, x=10, y=pdf.get_y(), w=pdf.w - 20)
    pdf.ln(80) # Adjust spacing as needed based on the image height

    # --- Analysis Sections ---
    # Using a two-column layout for better space utilization
    col_width = pdf.w / 2 - 15

    # --- Column 1 ---
    pdf.set_xy(10, pdf.get_y())

    # Technical Analysis
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(col_width, 10, 'Technical Analysis', 0, 2, 'L')
    pdf.set_font("Arial", '', 9)
    for key, value in technical_analysis.items():
        pdf.cell(col_width - 20, 5, sanitize(str(key)), 0, 0, 'L')
        pdf.cell(20, 5, sanitize(str(value)), 0, 1, 'R')
    pdf.ln(5)

    # DCF Analysis
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(col_width, 10, 'DCF Analysis', 0, 2, 'L')
    pdf.set_font("Arial", '', 9)
    for key, value in dcf_analysis.items():
        pdf.cell(col_width - 20, 5, sanitize(str(key)), 0, 0, 'L')
        pdf.cell(20, 5, sanitize(str(value)), 0, 1, 'R')
    pdf.ln(5)

    # Financial Health Scores
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(col_width, 10, 'Financial Health Scores', 0, 2, 'L')
    pdf.set_font("Arial", '', 9)
    pdf.cell(col_width - 20, 5, 'Beneish M-Score:', 0, 0, 'L')
    pdf.cell(20, 5, sanitize(m_score), 0, 1, 'R')
    pdf.cell(col_width - 20, 5, 'Piotroski F-Score:', 0, 0, 'L')
    pdf.cell(20, 5, sanitize(piotroski_score), 0, 1, 'R')
    pdf.ln(5)


    # --- Column 2 ---
    pdf.set_xy(pdf.w / 2, pdf.get_y() - 110) # Reset Y to align with top of column 1

    # Fundamental Analysis
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(col_width, 10, 'Fundamental Analysis', 0, 2, 'L')
    pdf.set_font("Arial", '', 9)
    for key, value in fundamental_analysis.items():
        pdf.cell(col_width - 20, 5, sanitize(str(key)), 0, 0, 'L')
        pdf.cell(20, 5, sanitize(str(value)), 0, 1, 'R')
    pdf.ln(5)

    # News & Sentiment Analysis
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(col_width, 10, 'News & Sentiment Analysis', 0, 2, 'L')
    pdf.set_font("Arial", '', 9)
    for key, value in news_sentiment.items():
        pdf.cell(col_width - 20, 5, sanitize(str(key)), 0, 0, 'L')
        pdf.cell(20, 5, sanitize(str(value)), 0, 1, 'R')
    pdf.ln(5)

    # Risk Analysis
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(col_width, 10, 'News-Based Risk Analysis', 0, 2, 'L')
    pdf.set_font("Arial", '', 9)
    for key, value in risk_analysis.items():
        # Using multi_cell for potentially longer risk descriptions
        pdf.multi_cell(col_width, 5, f"{sanitize(str(key))}: {sanitize(str(value))}", 0, 'L')
    pdf.ln(5)


    # --- Footer ---
    pdf.set_y(-15)
    pdf.set_font('Arial', 'I', 8)
    pdf.cell(0, 10, 'Page %s' % pdf.page_no(), 0, 0, 'C')
    pdf.cell(0, 10, 'Generated by StockMatrix - For informational purposes only.', 0, 0, 'R')

    # Return the PDF content as a byte string
    # 'S' destination returns the document as a string. latin-1 is needed for bytes output.
    return pdf.output(dest='S').encode('latin-1')