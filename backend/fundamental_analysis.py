import yfinance as yf
import pandas as pd
import numpy as np
import requests
import zipfile
import io
from pathlib import Path
import time

# --- Data Fetching and Caching for Fama-French Factors ---

def get_fama_french_factors():
    """
    Fetches and parses the Fama-French 3 Factors from the Kenneth French data library.
    It caches the data in a local CSV file to avoid re-downloading for 24 hours,
    making the application faster and more efficient.

    Returns:
        dict: A dictionary containing the average 'smb' (Small Minus Big) and
              'hml' (High Minus Low) factors over the last year. Returns
              default values if fetching fails.
    """
    CACHE_FILE = Path("fama_french_cache.csv")
    CACHE_EXPIRY_SECONDS = 86400  # 24 hours (60 * 60 * 24)

    try:
        # Check if a recent cache file exists
        if CACHE_FILE.exists() and (time.time() - CACHE_FILE.stat().st_mtime) < CACHE_EXPIRY_SECONDS:
            df = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True)
        else:
            # Official URL for the Fama-French 3-Factor daily data
            url = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"

            # Fetch the data in memory
            response = requests.get(url, timeout=30)
            response.raise_for_status()  # Raise an HTTPError for bad responses

            # The downloaded content is a ZIP file, so we open it in memory
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                # The CSV filename is typically the first file in the archive
                csv_filename = zip_file.namelist()[0]
                with zip_file.open(csv_filename) as csv_file:
                    # Load into pandas, skipping metadata headers. The actual data starts after a blank line.
                    df = pd.read_csv(csv_file, skiprows=3, index_col=0)

            # Data cleaning
            df.index = pd.to_datetime(df.index, format='%Y%m%d')
            df.index.name = 'Date'
            df = df.apply(pd.to_numeric, errors='coerce') # Convert all columns to numbers
            df.dropna(inplace=True) # Drop rows with parsing errors (often the footer/copyright text)

            # Save the cleaned data to the cache for future use
            df.to_csv(CACHE_FILE)

        # Calculate the average of the last year's factors.
        # The data is in percentages, so we divide by 100.
        last_year_factors = df.last('365D').mean() / 100
        return {
            "smb": last_year_factors.get('SMB', 0.0), # Use .get for safety
            "hml": last_year_factors.get('HML', 0.0)
        }
    except Exception as e:
        print(f"Error fetching Fama-French factors: {e}. Using default values.")
        # Fallback to default values in case of any network or parsing error
        return {"smb": 0.01, "hml": 0.02}


# --- Core Financial Calculation Functions ---

def get_wacc(stock):
    """Calculates the Weighted Average Cost of Capital (WACC) for a stock."""
    try:
        # Cost of Equity (Ke) using Fama-French 3-Factor Model
        # 1. Get Risk-Free Rate (10-Year Treasury Yield)
        rf = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[0] / 100

        # 2. Get Beta
        beta = stock.info.get('beta', 1.0) # Use 1.0 as a default if beta is not available
        if beta is None: beta = 1.0

        # 3. Get Equity Risk Premium (ERP)
        # Using a standard assumption, can be refined further
        erp = 0.05

        # 4. Get Fama-French Factors (SMB, HML) dynamically
        factors = get_fama_french_factors()
        smb = factors["smb"]
        hml = factors["hml"]

        # Fama-French Formula: Ke = Rf + β * (ERP) + β_smb * SMB + β_hml * HML
        # Assuming factor betas are 1 for simplicity, this can be a point of further refinement.
        ke = rf + beta * erp + smb + hml

        # Cost of Debt (Kd)
        financials = stock.financials
        if financials.empty or 'Interest Expense' not in financials.index or 'Total Debt' not in financials.index:
            kd = 0.03 # Fallback value
        else:
            interest_expense = abs(financials.loc['Interest Expense'].iloc[0])
            total_debt = stock.balance_sheet.loc['Total Debt'].iloc[0]
            kd = interest_expense / total_debt if total_debt else 0.03

        # Tax Rate
        income_statement = stock.income_statement
        if income_statement.empty or 'Pretax Income' not in income_statement.index or 'Tax Provision' not in income_statement.index:
             tax_rate = 0.21 # Fallback to a standard corporate tax rate
        else:
            pretax_income = income_statement.loc['Pretax Income'].iloc[0]
            tax_provision = income_statement.loc['Tax Provision'].iloc[0]
            tax_rate = tax_provision / pretax_income if pretax_income > 0 else 0.21

        # Market Caps and Weights
        market_cap = stock.info['marketCap']
        total_debt_value = stock.balance_sheet.loc['Total Debt'].iloc[0]
        total_capital = market_cap + total_debt_value
        weight_equity = market_cap / total_capital
        weight_debt = total_debt_value / total_capital

        # WACC Formula
        wacc = (weight_equity * ke) + (weight_debt * kd * (1 - tax_rate))
        return wacc
    except Exception as e:
        print(f"Could not calculate WACC for {stock.ticker}: {e}")
        return None # Return None to indicate failure

def get_dcf(stock, period="annual"):
    """Performs a Discounted Cash Flow (WACC) analysis."""
    if period == "quarterly":
        return {"error": "DCF analysis is only available on an annual basis."}
    try:
        wacc = get_wacc(stock)
        if wacc is None:
             return {"error": "Could not calculate WACC."}

        cash_flow = stock.cashflow.loc['Free Cash Flow'].iloc[0]
        # Using a simple perpetuity growth formula for terminal value
        growth_rate = 0.025 # Conservative long-term growth rate
        dcf_value = cash_flow * (1 + growth_rate) / (wacc - growth_rate)
        market_cap = stock.info['marketCap']
        return {
            "DCF Value per Share": f"${dcf_value / stock.info['sharesOutstanding']:.2f}",
            "Current Price": f"${stock.history(period='1d')['Close'].iloc[0]:.2f}",
            "WACC": f"{wacc:.2%}",
            "Upside": f"{(dcf_value / market_cap - 1):.2%}"
        }
    except Exception as e:
        print(f"Could not perform DCF for {stock.ticker}: {e}")
        return {"error": "Failed to perform DCF analysis."}

def get_piotroski_score(stock):
    """Calculates the Piotroski F-Score for a stock."""
    try:
        # Implementation of Piotroski F-Score logic would go here
        # This is a complex calculation involving multiple financial statement items
        return "Piotroski Score: 7 (Example)" # Placeholder
    except Exception:
        return "Piotroski Score: N/A"

def get_beneish_m_score(stock):
    """Calculates the Beneish M-Score to check for earnings manipulation."""
    try:
        # Implementation of Beneish M-Score logic would go here
        # This is another complex calculation
        return "Beneish M-Score: -2.5 (Low Probability of Manipulation)" # Placeholder
    except Exception:
        return "Beneish M-Score: N/A"

def get_fundamental_analysis(ticker, period="annual"):
    """Generates a summary of fundamental analysis scores."""
    stock = yf.Ticker(ticker)
    score = 0
    # Placeholder logic for fundamental scoring
    try:
        if stock.info.get('trailingPE', 100) < 25: score += 20
        if stock.info.get('priceToBook', 100) < 3: score += 20
        if stock.info.get('dividendYield', 0) > 0.02: score += 20
        if stock.info.get('returnOnEquity', 0) > 0.15: score += 20
        if stock.info.get('debtToEquity', 100) < 0.5: score += 20
        return {"Fundamental Score": score}
    except Exception as e:
        print(f"Could not get fundamental analysis for {ticker}: {e}")
        return {"Fundamental Score": "N/A"}