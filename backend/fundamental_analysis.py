# backend/fundamental_analysis.py
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import zipfile
import io
from pathlib import Path
import time
import logging

logger = logging.getLogger(__name__)

# --- Data Fetching and Caching for Fama-French Factors ---
def get_fama_french_factors():
    """
    Fetches and parses the Fama-French 3 Factors from the Kenneth French data library.
    It caches the data in a local CSV file to avoid re-downloading for 24 hours.
    """
    CACHE_FILE = Path("fama_french_cache.csv")
    CACHE_EXPIRY_SECONDS = 86400  # 24 hours

    try:
        if CACHE_FILE.exists() and (time.time() - CACHE_FILE.stat().st_mtime) < CACHE_EXPIRY_SECONDS:
            df = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True)
        else:
            url = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                csv_filename = zip_file.namelist()[0]
                with zip_file.open(csv_filename) as csv_file:
                    df = pd.read_csv(csv_file, skiprows=3, index_col=0)
            df.index = pd.to_datetime(df.index, format='%Y%m%d')
            df.index.name = 'Date'
            df = df.apply(pd.to_numeric, errors='coerce')
            df.dropna(inplace=True)
            df.to_csv(CACHE_FILE)

        last_year_factors = df.last('365D').mean() / 100
        return {
            "smb": last_year_factors.get('SMB', 0.0),
            "hml": last_year_factors.get('HML', 0.0)
        }
    except Exception as e:
        logger.error(f"Error fetching Fama-French factors: {e}. Using default values.")
        return {"smb": 0.01, "hml": 0.02}

# --- Core Financial Calculation Functions ---

def get_wacc(stock):
    """Calculates the Weighted Average Cost of Capital (WACC) for a stock."""
    try:
        # 1. Risk-Free Rate
        rf_ticker = yf.Ticker("^TNX")
        rf = rf_ticker.history(period="1d")['Close'].iloc[0] / 100

        # 2. Beta
        beta = stock.info.get('beta', 1.0)
        if beta is None: beta = 1.0

        # 3. Equity Risk Premium (ERP) & Fama-French Factors
        erp = 0.05
        factors = get_fama_french_factors()
        ke = rf + beta * erp + factors["smb"] + factors["hml"]

        # 4. Cost of Debt (Kd)
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        interest_expense = abs(financials.loc['Interest Expense'].iloc[0])
        total_debt = balance_sheet.loc['Total Debt'].iloc[0]
        kd = interest_expense / total_debt if total_debt else 0.03

        # 5. Tax Rate
        income_statement = stock.income_statement
        pretax_income = income_statement.loc['Pretax Income'].iloc[0]
        tax_provision = income_statement.loc['Tax Provision'].iloc[0]
        tax_rate = tax_provision / pretax_income if pretax_income > 0 else 0.21
        tax_rate = max(0.0, min(tax_rate, 0.40)) # Clamp tax rate

        # 6. Market Caps and Weights
        market_cap = stock.info['marketCap']
        total_capital = market_cap + total_debt
        weight_equity = market_cap / total_capital
        weight_debt = total_debt / total_capital

        # 7. WACC Formula
        wacc = (weight_equity * ke) + (weight_debt * kd * (1 - tax_rate))
        return wacc
    except Exception as e:
        logger.error(f"Could not calculate WACC for {stock.ticker}: {e}")
        return None

def get_dcf(stock, basis ="annual"):
    """Performs a Discounted Cash Flow (DCF) analysis."""
    if basis == "quarterly":
        return {"error": "DCF analysis is only available on an annual basis."}
    try:
        wacc = get_wacc(stock)
        if wacc is None:
             return {"error": "Could not calculate WACC, preventing DCF."}

        cash_flow = stock.cashflow.loc['Free Cash Flow'].iloc[0]
        growth_rate = 0.025

        if wacc <= growth_rate:
            return {"error": f"WACC ({wacc:.2%}) <= growth rate ({growth_rate:.2%}). Unreliable DCF."}

        dcf_value = cash_flow * (1 + growth_rate) / (wacc - growth_rate)
        market_cap = stock.info['marketCap']
        
        return {
            "DCF Value per Share": f"${dcf_value / stock.info['sharesOutstanding']:.2f}",
            "Current Price": f"${stock.history(period='1d')['Close'].iloc[0]:.2f}",
            "WACC": f"{wacc:.2%}",
            "Upside": f"{(dcf_value / market_cap - 1):.2%}"
        }
    except Exception as e:
        logger.error(f"Could not perform DCF for {stock.ticker}: {e}")
        return {"error": "Failed to perform DCF analysis due to missing data."}

def get_piotroski_score(stock):
    """
    Calculates the Piotroski F-Score, a 9-point scale to determine the
    financial strength of a company.
    """
    try:
        fs = stock.financials
        bs = stock.balance_sheet
        cf = stock.cashflow

        # Need 2 years of data for comparison
        if len(fs.columns) < 2 or len(bs.columns) < 2 or len(cf.columns) < 2:
            return {"error": "Not enough historical data for Piotroski score."}

        # --- Profitability Criteria (4 points) ---
        # 1. Net Income
        ni_y1 = fs.loc['Net Income'].iloc[0]
        f_score_ni = 1 if ni_y1 > 0 else 0

        # 2. Operating Cash Flow
        ocf_y1 = cf.loc['Operating Cash Flow'].iloc[0]
        f_score_ocf = 1 if ocf_y1 > 0 else 0

        # 3. Return on Assets (ROA)
        assets_y1 = bs.loc['Total Assets'].iloc[0]
        assets_y2 = bs.loc['Total Assets'].iloc[1]
        avg_assets = (assets_y1 + assets_y2) / 2
        roa_y1 = ni_y1 / avg_assets if avg_assets else 0
        ni_y2 = fs.loc['Net Income'].iloc[1]
        roa_y2 = ni_y2 / avg_assets if avg_assets else 0
        f_score_roa = 1 if roa_y1 > roa_y2 else 0
        
        # 4. Quality of Earnings (OCF vs NI)
        f_score_quality = 1 if ocf_y1 > ni_y1 else 0

        # --- Leverage, Liquidity, and Source of Funds Criteria (3 points) ---
        # 5. Change in Leverage (Long-term debt)
        debt_y1 = bs.loc['Long Term Debt'].iloc[0]
        debt_y2 = bs.loc['Long Term Debt'].iloc[1]
        leverage_y1 = debt_y1 / assets_y1 if assets_y1 else 0
        leverage_y2 = debt_y2 / assets_y2 if assets_y2 else 0
        f_score_lev = 1 if leverage_y1 < leverage_y2 else 0

        # 6. Change in Current Ratio
        curr_ratio_y1 = bs.loc['Current Assets'].iloc[0] / bs.loc['Current Liabilities'].iloc[0]
        curr_ratio_y2 = bs.loc['Current Assets'].iloc[1] / bs.loc['Current Liabilities'].iloc[1]
        f_score_liq = 1 if curr_ratio_y1 > curr_ratio_y2 else 0

        # 7. Change in Shares Outstanding
        shares_y1 = stock.info['sharesOutstanding']
        # Note: yfinance doesn't easily provide historical shares data in financials.
        # This is a limitation. We will assume no new shares issued.
        f_score_shares = 1 # Default to 1 (good) due to data limitation

        # --- Operating Efficiency Criteria (2 points) ---
        # 8. Change in Gross Margin
        gm_y1 = fs.loc['Gross Profit'].iloc[0] / fs.loc['Total Revenue'].iloc[0]
        gm_y2 = fs.loc['Gross Profit'].iloc[1] / fs.loc['Total Revenue'].iloc[1]
        f_score_margin = 1 if gm_y1 > gm_y2 else 0

        # 9. Change in Asset Turnover
        turnover_y1 = fs.loc['Total Revenue'].iloc[0] / avg_assets
        turnover_y2 = fs.loc['Total Revenue'].iloc[1] / avg_assets
        f_score_turn = 1 if turnover_y1 > turnover_y2 else 0
        
        # --- Final Score ---
        total_score = (f_score_ni + f_score_ocf + f_score_roa + f_score_quality +
                       f_score_lev + f_score_liq + f_score_shares +
                       f_score_margin + f_score_turn)
        
        verdict = "Strong" if total_score >= 8 else "Good" if total_score >= 5 else "Weak"

        return {"Piotroski F-Score": f"{total_score}/9", "Verdict": verdict}
    except (KeyError, IndexError) as e:
        return {"error": f"Missing financial data for Piotroski Score: {e}"}
    except Exception as e:
        logger.error(f"Piotroski calculation failed for {stock.ticker}: {e}")
        return {"error": "An unexpected error occurred during Piotroski calculation."}

# In backend/fundamental_analysis.py

def _safe_get(df, keys, year=0):
    """
    Safely gets a value from a DataFrame by trying multiple possible keys.
    Returns np.nan if no key is found.
    """
    for key in keys:
        if key in df.index:
            return df.loc[key].iloc[year]
    return np.nan # Return Not-a-Number if no key is found


def get_beneish_m_score(stock):
    """
    Calculates the Beneish M-Score. Now updated to handle missing data gracefully.
    """
    try:
        fs = stock.financials
        bs = stock.balance_sheet
        cf = stock.cashflow

        # Need 2 years of data for comparison
        if len(fs.columns) < 2 or len(bs.columns) < 2:
            return {"error": "Not enough historical data for Beneish score."}

        # --- Data Extraction using the _safe_get helper ---
        # Define possible names for each required line item
        rec_keys = ['Accounts Receivable']
        sales_keys = ['Total Revenue']
        cogs_keys = ['Cost Of Revenue']
        assets_keys = ['Total Assets']
        ppe_keys = ['Property Plant And Equipment', 'Net Property, Plant and Equipment']
        dep_keys = ['Depreciation And Amortization', 'Depreciation']
        sga_keys = ['Selling General And Administration', 'Selling General and Administrative Expenses']
        debt_keys = ['Total Debt']
        ni_keys = ['Net Income']
        cfo_keys = ['Operating Cash Flow', 'Cash Flow from Operations']

        # Year 1 (t) data
        rec_y1 = _safe_get(bs, rec_keys, 0)
        sales_y1 = _safe_get(fs, sales_keys, 0)
        cogs_y1 = _safe_get(fs, cogs_keys, 0)
        assets_y1 = _safe_get(bs, assets_keys, 0)
        ppe_y1 = _safe_get(bs, ppe_keys, 0)
        dep_y1 = _safe_get(cf, dep_keys, 0)
        sga_y1 = _safe_get(fs, sga_keys, 0)
        debt_y1 = _safe_get(bs, debt_keys, 0)
        ni_y1 = _safe_get(fs, ni_keys, 0)
        cfo_y1 = _safe_get(cf, cfo_keys, 0)

        # Year 2 (t-1) data
        rec_y2 = _safe_get(bs, rec_keys, 1)
        sales_y2 = _safe_get(fs, sales_keys, 1)
        cogs_y2 = _safe_get(fs, cogs_keys, 1)
        assets_y2 = _safe_get(bs, assets_keys, 1)
        ppe_y2 = _safe_get(bs, ppe_keys, 1)
        dep_y2 = _safe_get(cf, dep_keys, 1)
        sga_y2 = _safe_get(fs, sga_keys, 1)
        debt_y2 = _safe_get(bs, debt_keys, 1)

        # Check if any crucial data is missing after trying all keys
        if any(pd.isna(v) for v in [rec_y1, sales_y1, cogs_y1, assets_y1, ppe_y1, dep_y1, sga_y1, debt_y1, ni_y1, cfo_y1]):
             return {"error": "Could not calculate Beneish Score due to missing financial data (e.g., PPE, SGA)."}

        # --- The rest of the calculation is the same ---
        # 1. DSRI (Days Sales in Receivables Index)
        dsri = (rec_y1 / sales_y1) / (rec_y2 / sales_y2)

# 2. GMI (Gross Margin Index)
        gm_y1 = (sales_y1 - cogs_y1) / sales_y1
        gm_y2 = (sales_y2 - cogs_y2) / sales_y2
        gmi = gm_y2 / gm_y1

        # 3. AQI (Asset Quality Index)
        non_curr_assets_y1 = assets_y1 - bs.loc['Current Assets'].iloc[0]
        non_curr_assets_y2 = assets_y2 - bs.loc['Current Assets'].iloc[1]
        aqi = (non_curr_assets_y1 / assets_y1) / (non_curr_assets_y2 / assets_y2)

        # 4. SGI (Sales Growth Index)
        sgi = sales_y1 / sales_y2

        # 5. DEPI (Depreciation Index)
        depi = (dep_y2 / (ppe_y2 + dep_y2)) / (dep_y1 / (ppe_y1 + dep_y1))

        # 6. SGAI (SG&A Index)
        sgai = (sga_y1 / sales_y1) / (sga_y2 / sales_y2)

        # 7. LVGI (Leverage Index)
        lvgi = (debt_y1 / assets_y1) / (debt_y2 / assets_y2)

        # 8. TATA (Total Accruals to Total Assets)
        accruals = ni_y1 - cfo_y1
        tata = accruals / assets_y1

        # Beneish M-Score Formula
        m_score = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi +
                   0.892 * sgi + 0.115 * depi - 0.172 * sgai +
                   4.679 * tata - 0.327 * lvgi)

        verdict = "Potential Manipulator" if m_score > -1.78 else "Unlikely Manipulator"

        return {"Beneish M-Score": f"{m_score:.4f}", "Verdict": verdict}

    except Exception as e:
        logger.error(f"Beneish calculation failed for {stock.ticker}: {e}", exc_info=True)
        return {"error": "An unexpected error occurred during Beneish calculation."}

def analyze_fundamentals(ticker, basis ="annual"):
    """Generates a summary of fundamental analysis scores."""
    stock = yf.Ticker(ticker)
    score = 0
    try:
        if stock.info.get('trailingPE', 100) < 25: score += 20
        if stock.info.get('priceToBook', 100) < 3: score += 20
        if stock.info.get('dividendYield', 0) > 0.02: score += 20
        if stock.info.get('returnOnEquity', 0) > 0.15: score += 20
        if stock.info.get('debtToEquity', 100) < 0.5: score += 20
        
        # Combine all fundamental results
        results = {"Fundamental Score": score}
        results.update(get_dcf(stock, basis))
        results.update(get_piotroski_score(stock))
        results.update(get_beneish_m_score(stock))

        return results
    except Exception as e:
        logger.error(f"Could not get fundamental analysis for {ticker}: {e}")
        return {"error": "Fundamental analysis failed to execute."}