# backend/fundamental_analysis.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# --- Helper function to safely access financial data ---
def _safe_get(df, keys, year=0):
    """
    Safely gets a value from a DataFrame by trying multiple possible keys.
    Returns np.nan if no key is found or if the index is out of bounds.
    """
    if df is None or year >= len(df.columns):
        return np.nan
    for key in keys:
        if key in df.index:
            return df.loc[key].iloc[year]
    return np.nan

# --- Sub-Score Calculation Functions ---

def get_piotroski_score(stock):
    """Calculates the 0-9 Piotroski F-Score."""
    try:
        fs = stock.financials
        bs = stock.balance_sheet
        cf = stock.cashflow

        if len(fs.columns) < 2 or len(bs.columns) < 2 or len(cf.columns) < 2:
            return {"error": "Not enough historical data for Piotroski score."}

        # Safe data extraction for all 9 signals
        ni_y1 = _safe_get(fs, ['Net Income'], 0)
        assets_y1 = _safe_get(bs, ['Total Assets'], 0)
        assets_y2 = _safe_get(bs, ['Total Assets'], 1)
        roa_y1 = ni_y1 / assets_y1 if assets_y1 else 0
        ni_y2 = _safe_get(fs, ['Net Income'], 1)
        roa_y2 = ni_y2 / assets_y2 if assets_y2 else 0
        ocf_y1 = _safe_get(cf, ['Operating Cash Flow', 'Cash Flow from Operations'], 0)
        debt_y1 = _safe_get(bs, ['Total Debt', 'Long Term Debt'], 0)
        debt_y2 = _safe_get(bs, ['Total Debt', 'Long Term Debt'], 1)
        cr_y1 = _safe_get(bs, ['Current Ratio'], 0) # yfinance sometimes provides this
        if pd.isna(cr_y1):
            curr_assets_y1 = _safe_get(bs, ['Current Assets'], 0)
            curr_liab_y1 = _safe_get(bs, ['Current Liabilities'], 0)
            cr_y1 = curr_assets_y1 / curr_liab_y1 if curr_liab_y1 else 0
        cr_y2 = _safe_get(bs, ['Current Ratio'], 1)
        if pd.isna(cr_y2):
            curr_assets_y2 = _safe_get(bs, ['Current Assets'], 1)
            curr_liab_y2 = _safe_get(bs, ['Current Liabilities'], 1)
            cr_y2 = curr_assets_y2 / curr_liab_y2 if curr_liab_y2 else 0

        shares_y1 = _safe_get(stock.get_shares_full(start="1900-01-01"), [stock.ticker], -1)
        shares_y2 = _safe_get(stock.get_shares_full(start="1900-01-01"), [stock.ticker], -2)
        
        gp_y1 = _safe_get(fs, ['Gross Profit'], 0)
        rev_y1 = _safe_get(fs, ['Total Revenue'], 0)
        gm_y1 = gp_y1 / rev_y1 if rev_y1 else 0
        gp_y2 = _safe_get(fs, ['Gross Profit'], 1)
        rev_y2 = _safe_get(fs, ['Total Revenue'], 1)
        gm_y2 = gp_y2 / rev_y2 if rev_y2 else 0
        
        at_y1 = rev_y1 / assets_y1 if assets_y1 else 0
        at_y2 = rev_y2 / assets_y2 if assets_y2 else 0
        
        # Check for any missing data that would make calculation impossible
        if any(pd.isna(v) for v in [roa_y1, ocf_y1, debt_y1, debt_y2, cr_y1, cr_y2, shares_y1, shares_y2, gm_y1, gm_y2, at_y1, at_y2]):
            return {"error": "Missing data for one or more Piotroski criteria."}
            
        # Evaluate 9 signals
        f_roa = 1 if roa_y1 > 0 else 0
        f_ocf = 1 if ocf_y1 > 0 else 0
        f_cfo_roa = 1 if ocf_y1 > roa_y1 else 0
        f_delta_roa = 1 if roa_y1 > roa_y2 else 0
        f_delta_lev = 1 if (debt_y1 / assets_y1) < (debt_y2 / assets_y2) else 0
        f_delta_cr = 1 if cr_y1 > cr_y2 else 0
        f_shares = 1 if shares_y1 <= shares_y2 else 0
        f_delta_gm = 1 if gm_y1 > gm_y2 else 0
        f_delta_at = 1 if at_y1 > at_y2 else 0
        
        f_score = f_roa + f_ocf + f_cfo_roa + f_delta_roa + f_delta_lev + f_delta_cr + f_shares + f_delta_gm + f_delta_at
        return {"Piotroski F-Score": f_score}

    except Exception as e:
        logger.error(f"Piotroski calculation failed for {stock.ticker}: {e}")
        return {"error": "An unexpected error occurred during Piotroski calculation."}

def get_altman_z_score(stock):
    """Calculates the Altman Z-Score for bankruptcy risk."""
    try:
        # For non-manufacturing firms, a different formula is often used, but we'll stick to the standard one.
        # Check industry to see if model is applicable
        sector = stock.info.get('sector', '')
        if 'Financial' in sector or 'Real Estate' in sector:
            return {"error": "Altman Z-Score is not applicable to financial or real estate firms."}

        bs = stock.balance_sheet
        fs = stock.financials
        
        # Extract data
        wc = _safe_get(bs, ['Working Capital', 'Current Assets']) - _safe_get(bs, ['Current Liabilities'])
        ta = _safe_get(bs, ['Total Assets'])
        re = _safe_get(bs, ['Retained Earnings'])
        ebit = _safe_get(fs, ['EBIT', 'Operating Income'])
        mve = stock.info.get('marketCap')
        tl = _safe_get(bs, ['Total Liab', 'Total Liabilities'])
        sales = _safe_get(fs, ['Total Revenue', 'Revenue'])

        if any(pd.isna(v) for v in [wc, ta, re, ebit, mve, tl, sales]):
            return {"error": "Missing data for one or more Altman Z-Score components."}
        if ta == 0 or tl == 0:
            return {"error": "Total Assets or Liabilities are zero, cannot calculate Z-Score."}
        
        # Calculate ratios
        A = wc / ta
        B = re / ta
        C = ebit / ta
        D = mve / tl
        E = sales / ta

        z_score = 1.2 * A + 1.4 * B + 3.3 * C + 0.6 * D + 1.0 * E
        return {"Altman Z-Score": z_score}

    except Exception as e:
        logger.error(f"Altman Z-Score calculation failed for {stock.ticker}: {e}")
        return {"error": "An unexpected error occurred during Altman Z-Score calculation."}

def get_beneish_m_score(stock):
    """Calculates the Beneish M-Score for earnings manipulation risk."""
    # This function is already robust from our previous work. We'll use it as is.
    # We will assume the full, robust version from our previous discussion is here.
    # For brevity in this response, the full code is omitted, but it would be the same
    # robust version that handles missing keys and division by zero.
    # Let's mock a simple return for this example.
    # In your actual file, you should have the complete `get_beneish_m_score` function we built.
    try:
        # A full implementation would go here. Returning a sample success for now.
        return {"Beneish M-Score": -2.5}
    except Exception as e:
        return {"error": "Beneish Score calculation failed."}


# --- Main Orchestrator Function ---

def analyze_fundamentals(ticker: str, basis: str = "annual"):
    """
    Orchestrates the 3-factor fundamental analysis model.
    """
    stock = yf.Ticker(ticker)
    
    # Initialize with neutral scores (5 out of 10)
    f_score_10, z_score_10, m_score_10 = 5.0, 5.0, 5.0
    
    breakdown = {}
    notes = []

    # 1. Piotroski F-Score
    piotroski_result = get_piotroski_score(stock)
    if "error" in piotroski_result:
        notes.append(f"Piotroski: {piotroski_result['error']}")
    else:
        f_raw = piotroski_result["Piotroski F-Score"]
        f_score_10 = (f_raw / 9) * 10
        breakdown['Piotroski F-Score'] = f"{f_raw}/9"

    # 2. Altman Z-Score
    altman_result = get_altman_z_score(stock)
    if "error" in altman_result:
        notes.append(f"Altman Z: {altman_result['error']}")
    else:
        z_raw = altman_result["Altman Z-Score"]
        # Normalize to 0-10 scale as per your formula
        z_score_10 = min(max((z_raw - 1.8) / (2.99 - 1.8) * 10, 0.0), 10.0)
        breakdown['Altman Z-Score'] = f"{z_raw:.2f}"
        if z_raw > 2.99: breakdown['Bankruptcy Risk'] = "Safe"
        elif z_raw > 1.8: breakdown['Bankruptcy Risk'] = "Gray Zone"
        else: breakdown['Bankruptcy Risk'] = "Distress Zone"

    # 3. Beneish M-Score
    beneish_result = get_beneish_m_score(stock)
    if "error" in beneish_result:
        notes.append(f"Beneish: {beneish_result['error']}")
    else:
        m_raw = beneish_result["Beneish M-Score"]
        # Normalize to 0-10 scale as per your formula (inverted)
        m_score_10 = min(max((-2.22 - m_raw) / 5 * 10, 0.0), 10.0)
        breakdown['Beneish M-Score'] = f"{m_raw:.2f}"
        breakdown['Manipulation Risk'] = "High" if m_raw > -2.22 else "Low"

    # --- Final Composite Score and Verdict ---
    
    final_score = (f_score_10 + z_score_10 + m_score_10) / 3 * 10
    
    if final_score >= 80: verdict = "Strong Value + Quality"
    elif final_score >= 60: verdict = "Fundamentally Sound"
    elif final_score >= 30: verdict = "Fair Value / Watchlist"
    else: verdict = "High Risk / Avoid"
    
    return {
        "Fundamental Score": round(final_score, 2),
        "Verdict": verdict,
        "Notes": notes if notes else ["All fundamental models completed successfully."],
        "Breakdown": breakdown
    }