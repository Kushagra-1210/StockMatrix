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

# --- Helper function to safely access financial data ---
def _safe_get(df, keys, year=0):
    """
    Safely gets a value from a DataFrame by trying multiple possible keys.
    Returns np.nan if no key is found or if the index is out of bounds.
    """
    if year >= len(df.columns):
        return np.nan
    for key in keys:
        if key in df.index:
            return df.loc[key].iloc[year]
    return np.nan

# --- Fama-French data fetching (no changes needed here) ---
def get_fama_french_factors():
    # ... (this function is already robust)
    CACHE_FILE = Path("fama_french_cache.csv")
    CACHE_EXPIRY_SECONDS = 86400
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
        return {"smb": last_year_factors.get('SMB', 0.0), "hml": last_year_factors.get('HML', 0.0)}
    except Exception as e:
        logger.error(f"Error fetching Fama-French factors: {e}. Using default values.")
        return {"smb": 0.01, "hml": 0.02}

# --- REFACTORED Core Financial Calculation Functions ---

def get_wacc(stock):
    """Calculates WACC, now with robust data handling."""
    try:
        info = stock.info
        financials = stock.financials
        balance_sheet = stock.balance_sheet

        # 1. Risk-Free Rate
        rf = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[0] / 100

        # 2. Beta
        beta = info.get('beta', 1.0)
        if beta is None: beta = 1.0

        # 3. Cost of Equity
        erp = 0.05
        factors = get_fama_french_factors()
        ke = rf + beta * erp + factors["smb"] + factors["hml"]

        # 4. Cost of Debt (safely accessed)
        interest_expense = abs(_safe_get(financials, ['Interest Expense']))
        total_debt = _safe_get(balance_sheet, ['Total Debt'])
        if pd.isna(interest_expense) or pd.isna(total_debt):
            return {"error": "Missing Interest Expense or Total Debt for WACC."}
        kd = interest_expense / total_debt if total_debt else 0.03

        # 5. Tax Rate (safely accessed)
        pretax_income = _safe_get(financials, ['Pretax Income'])
        tax_provision = _safe_get(financials, ['Tax Provision'])
        if pd.isna(pretax_income) or pd.isna(tax_provision):
            return {"error": "Missing income or tax data for WACC."}
        tax_rate = tax_provision / pretax_income if pretax_income > 0 else 0.21
        tax_rate = max(0.0, min(tax_rate, 0.40))

        # 6. Market Caps and Weights
        market_cap = info['marketCap']
        total_capital = market_cap + total_debt
        weight_equity = market_cap / total_capital
        weight_debt = total_debt / total_capital

        # 7. WACC Formula
        wacc = (weight_equity * ke) + (weight_debt * kd * (1 - tax_rate))
        return wacc
    except Exception as e:
        logger.error(f"Could not calculate WACC for {stock.ticker}: {e}")
        return None # Return None on failure

def get_dcf(stock, basis="annual"):
    """Performs DCF analysis, now with robust data handling."""
    if basis == "quarterly":
        return {"error": "DCF analysis is only available on an annual basis."}
    try:
        wacc = get_wacc(stock)
        if wacc is None:
             return {"error": "Could not calculate WACC, preventing DCF."}

        cash_flow = _safe_get(stock.cashflow, ['Free Cash Flow'])
        if pd.isna(cash_flow):
            return {"error": "Free Cash Flow data not available for DCF."}

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
    """Calculates Piotroski F-Score with robust data handling."""
    try:
        fs = stock.financials
        bs = stock.balance_sheet
        cf = stock.cashflow

        if len(fs.columns) < 2 or len(bs.columns) < 2 or len(cf.columns) < 2:
            return {"error": "Not enough historical data for Piotroski score."}

        # Safe data extraction
        ni_y1 = _safe_get(fs, ['Net Income'], 0)
        ni_y2 = _safe_get(fs, ['Net Income'], 1)
        ocf_y1 = _safe_get(cf, ['Operating Cash Flow', 'Cash Flow from Operations'], 0)
        assets_y1 = _safe_get(bs, ['Total Assets'], 0)
        assets_y2 = _safe_get(bs, ['Total Assets'], 1)
        debt_y1 = _safe_get(bs, ['Long Term Debt'], 0)
        debt_y2 = _safe_get(bs, ['Long Term Debt'], 1)
        curr_assets_y1 = _safe_get(bs, ['Current Assets'], 0)
        curr_liab_y1 = _safe_get(bs, ['Current Liabilities'], 0)
        curr_assets_y2 = _safe_get(bs, ['Current Assets'], 1)
        curr_liab_y2 = _safe_get(bs, ['Current Liabilities'], 1)
        revenue_y1 = _safe_get(fs, ['Total Revenue'], 0)
        revenue_y2 = _safe_get(fs, ['Total Revenue'], 1)
        gp_y1 = _safe_get(fs, ['Gross Profit'], 0)
        gp_y2 = _safe_get(fs, ['Gross Profit'], 1)
        
        # Check for missing crucial data
        if any(pd.isna(v) for v in [ni_y1, ni_y2, ocf_y1, assets_y1, assets_y2, debt_y1, debt_y2,
                                     curr_assets_y1, curr_liab_y1, curr_assets_y2, curr_liab_y2,
                                     revenue_y1, revenue_y2, gp_y1, gp_y2]):
            return {"error": "Missing critical data for Piotroski score (e.g., Net Income, Assets)."}

        # Calculations (with checks for division by zero)
        f_score_ni = 1 if ni_y1 > 0 else 0
        f_score_ocf = 1 if ocf_y1 > 0 else 0
        avg_assets = (assets_y1 + assets_y2) / 2
        roa_y1 = ni_y1 / avg_assets if avg_assets else 0
        roa_y2 = ni_y2 / avg_assets if avg_assets else 0
        f_score_roa = 1 if roa_y1 > roa_y2 else 0
        f_score_quality = 1 if ocf_y1 > ni_y1 else 0
        leverage_y1 = debt_y1 / assets_y1 if assets_y1 else 0
        leverage_y2 = debt_y2 / assets_y2 if assets_y2 else 0
        f_score_lev = 1 if leverage_y1 < leverage_y2 else 0
        curr_ratio_y1 = curr_assets_y1 / curr_liab_y1 if curr_liab_y1 else 0
        curr_ratio_y2 = curr_assets_y2 / curr_liab_y2 if curr_liab_y2 else 0
        f_score_liq = 1 if curr_ratio_y1 > curr_ratio_y2 else 0
        f_score_shares = 1 # Limitation: Assume no share dilution
        gm_y1 = gp_y1 / revenue_y1 if revenue_y1 else 0
        gm_y2 = gp_y2 / revenue_y2 if revenue_y2 else 0
        f_score_margin = 1 if gm_y1 > gm_y2 else 0
        turnover_y1 = revenue_y1 / avg_assets if avg_assets else 0
        turnover_y2 = revenue_y2 / avg_assets if avg_assets else 0
        f_score_turn = 1 if turnover_y1 > turnover_y2 else 0
        
        total_score = (f_score_ni + f_score_ocf + f_score_roa + f_score_quality +
                       f_score_lev + f_score_liq + f_score_shares +
                       f_score_margin + f_score_turn)
        
        verdict = "Strong" if total_score >= 8 else "Good" if total_score >= 5 else "Weak"
        return {"Piotroski F-Score": f"{total_score}/9", "Verdict": verdict}
    except Exception as e:
        logger.error(f"Piotroski calculation failed for {stock.ticker}: {e}")
        return {"error": "An unexpected error occurred during Piotroski calculation."}

def get_beneish_m_score(stock):
    """Calculates Beneish M-Score, now with robust data handling and validation."""
    try:
        fs = stock.financials
        bs = stock.balance_sheet
        cf = stock.cashflow

        if len(fs.columns) < 2 or len(bs.columns) < 2:
            return {"error": "Not enough historical data for Beneish score."}
        
        rec_keys = ['Accounts Receivable']
        sales_keys = ['Total Revenue', 'Revenue']
        cogs_keys = ['Cost Of Revenue', 'Cost of Goods Sold']
        assets_keys = ['Total Assets']
        ppe_keys = ['Property Plant And Equipment', 'Net Property, Plant and Equipment', 'Fixed Assets', 'Gross Block']
        dep_keys = ['Depreciation And Amortization', 'Depreciation']
        sga_keys = ['Selling General And Administration', 'Selling General and Administrative Expenses', 'Administrative and selling expenses']
        debt_keys = ['Total Debt']
        ni_keys = ['Net Income']
        cfo_keys = ['Operating Cash Flow', 'Cash Flow from Operations']
        curr_assets_keys = ['Current Assets']

        # Extract data safely
        data_points = [
            _safe_get(bs, rec_keys, 0), _safe_get(fs, sales_keys, 0), _safe_get(fs, cogs_keys, 0),
            _safe_get(bs, assets_keys, 0), _safe_get(bs, ppe_keys, 0), _safe_get(cf, dep_keys, 0),
            _safe_get(fs, sga_keys, 0), _safe_get(bs, debt_keys, 0), _safe_get(fs, ni_keys, 0),
            _safe_get(cf, cfo_keys, 0), _safe_get(bs, rec_keys, 1), _safe_get(fs, sales_keys, 1),
            _safe_get(fs, cogs_keys, 1), _safe_get(bs, assets_keys, 1), _safe_get(bs, ppe_keys, 1),
            _safe_get(cf, dep_keys, 1), _safe_get(fs, sga_keys, 1), _safe_get(bs, debt_keys, 1),
            _safe_get(bs, curr_assets_keys, 0), _safe_get(bs, curr_assets_keys, 1)
        ]

        if any(pd.isna(v) for v in data_points):
             return {"error": "Could not calculate Beneish Score due to missing financial data."}
        
        (rec_y1, sales_y1, cogs_y1, assets_y1, ppe_y1, dep_y1, sga_y1, debt_y1, ni_y1, cfo_y1,
         rec_y2, sales_y2, cogs_y2, assets_y2, ppe_y2, dep_y2, sga_y2, debt_y2,
         curr_assets_y1, curr_assets_y2) = data_points

        # Calculate indices with division-by-zero checks
        dsri = (rec_y1 / sales_y1) / (rec_y2 / sales_y2) if sales_y1 and sales_y2 else 1.0
        gm_y1 = (sales_y1 - cogs_y1) / sales_y1 if sales_y1 else 0
        gm_y2 = (sales_y2 - cogs_y2) / sales_y2 if sales_y2 else 0
        gmi = gm_y2 / gm_y1 if gm_y1 else 1.0
        aqi = ((assets_y1 - curr_assets_y1) / assets_y1) / ((assets_y2 - curr_assets_y2) / assets_y2) if assets_y1 and assets_y2 else 1.0
        sgi = sales_y1 / sales_y2 if sales_y2 else 1.0
        depi = (dep_y2 / (ppe_y2 + dep_y2) if (ppe_y2 + dep_y2) else 0) / (dep_y1 / (ppe_y1 + dep_y1) if (ppe_y1 + dep_y1) else 1)
        sgai = (sga_y1 / sales_y1) / (sga_y2 / sales_y2) if sales_y1 and sales_y2 else 1.0
        lvgi = (debt_y1 / assets_y1) / (debt_y2 / assets_y2) if assets_y1 and assets_y2 and debt_y2 else 1.0
        tata = (ni_y1 - cfo_y1) / assets_y1 if assets_y1 else 0.0

        indices = [dsri, gmi, aqi, sgi, depi, sgai, lvgi, tata]
        if not all(np.isfinite(v) for v in indices):
            return {"error": "Could not calculate Beneish Score due to invalid intermediate values."}

        # Beneish M-Score Formula
        m_score = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi +
                   0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)
        
        verdict = "Potential Manipulator" if m_score > -1.78 else "Unlikely Manipulator"
        return {"Beneish M-Score": f"{m_score:.4f}", "Verdict": verdict}

    except Exception as e:
        logger.error(f"Beneish calculation failed for {stock.ticker}: {e}", exc_info=True)
        return {"error": "An unexpected error occurred during Beneish calculation."}

# --- Main Analysis Function ---
def analyze_fundamentals(ticker, basis="annual"):
    """Generates a summary of fundamental analysis scores."""
    stock = yf.Ticker(ticker)
    results = {}
    try:
        # Combine all fundamental results
        results.update(get_dcf(stock, basis))
        results.update(get_piotroski_score(stock))
        results.update(get_beneish_m_score(stock))
        return results
    except Exception as e:
        logger.error(f"Could not get fundamental analysis for {ticker}: {e}")
        return {"error": "Fundamental analysis failed to execute."}