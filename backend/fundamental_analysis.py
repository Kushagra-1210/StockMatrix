# backend/fundamental_analysis.py
import pandas as pd
import numpy as np
import logging
from backend.data_provider import DataProvider # Import the new DataProvider

logger = logging.getLogger(__name__)

# --- Helper functions to safely access financial data ---
# These helpers remain the same as they are still useful.
def _safe_get(df, keys, year=0):
    if df is None or df.empty or year >= len(df.columns):
        return np.nan
    for key in keys:
        if key in df.index:
            value = df.loc[key].iloc[year]
            if pd.notna(value):
                return value
    return np.nan

def _safe_fmp_get(fmp_data_dict, statement_type, key, year=0):
    statement = fmp_data_dict.get(statement_type)
    if statement and isinstance(statement, list) and len(statement) > year:
        if isinstance(statement[year], dict):
            return statement[year].get(key)
    return np.nan

# --- Sub-Score Calculation Functions (Refactored) ---
# Note: The function signatures have changed. They now accept the specific data they need.

def get_piotroski_score(fs, bs, cf, info, fmp_data):
    """Calculates the 0-9 Piotroski F-Score with intelligent data fallbacks."""
    try:
        if len(fs.columns) < 2 or len(bs.columns) < 2 or len(cf.columns) < 2:
            if not fmp_data.get('income_statement') or len(fmp_data['income_statement']) < 2:
                return {"error": "Not enough historical data for Piotroski score."}

        # --- Data Extraction ---
        ni_y1 = _safe_get(fs, ['Net Income'], 0) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', 0)
        assets_y1 = _safe_get(bs, ['Total Assets'], 0) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', 0)
        roa_y1 = ni_y1 / assets_y1 if assets_y1 and ni_y1 is not None else 0

        ni_y2 = _safe_get(fs, ['Net Income'], 1) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', 1)
        assets_y2 = _safe_get(bs, ['Total Assets'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', 1)
        roa_y2 = ni_y2 / assets_y2 if assets_y2 and ni_y2 is not None else 0
        
        # ... (The rest of the data extraction and calculation logic remains the same)
        ocf_y1 = _safe_get(cf, ['Operating Cash Flow', 'Cash Flow from Operations'], 0) or _safe_fmp_get(fmp_data, 'cash_flow', 'operatingCashFlow', 0)
        rev_y1 = _safe_get(fs, ['Total Revenue'], 0) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', 0)
        cogs_y1 = _safe_get(fs, ['Cost Of Revenue'], 0) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', 0)
        gp_y1 = rev_y1 - cogs_y1 if rev_y1 is not None and cogs_y1 is not None else _safe_get(fs, ['Gross Profit'], 0)
        gm_y1 = gp_y1 / rev_y1 if rev_y1 and gp_y1 is not None else 0
        
        rev_y2 = _safe_get(fs, ['Total Revenue'], 1) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', 1)
        cogs_y2 = _safe_get(fs, ['Cost Of Revenue'], 1) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', 1)
        gp_y2 = rev_y2 - cogs_y2 if rev_y2 is not None and cogs_y2 is not None else _safe_get(fs, ['Gross Profit'], 1)
        gm_y2 = gp_y2 / rev_y2 if rev_y2 and gp_y2 is not None else 0

        debt_y1 = _safe_get(bs, ['Total Debt', 'Long Term Debt'], 0) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', 0)
        debt_y2 = _safe_get(bs, ['Total Debt', 'Long Term Debt'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', 1)

        curr_assets_y1 = _safe_get(bs, ['Current Assets'], 0) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', 0)
        curr_liab_y1 = _safe_get(bs, ['Current Liabilities'], 0) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', 0)
        cr_y1 = curr_assets_y1 / curr_liab_y1 if curr_liab_y1 and curr_assets_y1 is not None else 0

        curr_assets_y2 = _safe_get(bs, ['Current Assets'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', 1)
        curr_liab_y2 = _safe_get(bs, ['Current Liabilities'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', 1)
        cr_y2 = curr_assets_y2 / curr_liab_y2 if curr_liab_y2 and curr_assets_y2 is not None else 0
        
        shares_y1 = info.get('sharesOutstanding')
        shares_y2 = shares_y1 

        data_points = [roa_y1, ocf_y1, debt_y1, debt_y2, cr_y1, cr_y2, shares_y1, shares_y2, gm_y1, gm_y2]
        if any(v is None or pd.isna(v) for v in data_points):
            return {"error": "Missing non-calculable critical data for Piotroski."}
            
        f_roa = 1 if roa_y1 > 0 else 0
        f_ocf = 1 if ocf_y1 > 0 else 0
        f_cfo_roa = 1 if ocf_y1 > roa_y1 else 0
        f_delta_roa = 1 if roa_y1 > roa_y2 else 0
        f_delta_lev = 1 if (debt_y1 / assets_y1 if assets_y1 else 0) < (debt_y2 / assets_y2 if assets_y2 else 0) else 0
        f_delta_cr = 1 if cr_y1 > cr_y2 else 0
        f_shares = 1 if shares_y1 <= shares_y2 else 0
        f_delta_gm = 1 if gm_y1 > gm_y2 else 0
        at_y1 = rev_y1 / assets_y1 if assets_y1 else 0
        at_y2 = rev_y2 / assets_y2 if assets_y2 else 0
        f_delta_at = 1 if at_y1 > at_y2 else 0
        
        f_score = sum([f_roa, f_ocf, f_cfo_roa, f_delta_roa, f_delta_lev, f_delta_cr, f_shares, f_delta_gm, f_delta_at])
        return {"Piotroski F-Score": f_score}

    except Exception as e:
        logger.error(f"Piotroski calculation failed: {e}")
        return {"error": "An unexpected error occurred during Piotroski calculation."}

# ... (The get_altman_z_score and get_beneish_m_score functions would be refactored similarly)
# ... I will omit them here for brevity but the principle is the same:
# ... change the function signature and use the passed-in data.

def get_altman_z_score(fs, bs, info, fmp_data):
    """Calculates the Altman Z-Score with intelligent data fallbacks."""
    try:
        sector = info.get('sector', '')
        if 'Financial' in sector or 'Real Estate' in sector:
            return {"error": "Altman Z-Score not applicable to financial/real estate firms."}

        ta = _safe_get(bs, ['Total Assets']) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', 0)
        wc = _safe_get(bs, ['Working Capital'])
        if pd.isna(wc):
            current_assets = _safe_get(bs, ['Current Assets']) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', 0)
            current_liabilities = _safe_get(bs, ['Current Liabilities']) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', 0)
            wc = current_assets - current_liabilities
            
        re = _safe_get(bs, ['Retained Earnings']) or _safe_fmp_get(fmp_data, 'balance_sheet', 'retainedEarnings', 0)
        ebit = _safe_get(fs, ['EBIT', 'Operating Income'])
        if pd.isna(ebit):
            ni = _safe_get(fs, ['Net Income'])
            interest = _safe_get(fs, ['Interest Expense'], 0)
            taxes = _safe_get(fs, ['Tax Provision'], 0)
            ebit = ni + interest + taxes if all(pd.notna([ni, interest, taxes])) else _safe_fmp_get(fmp_data, 'income_statement', 'operatingIncome', 0)
            
        mve = info.get('marketCap') or _safe_fmp_get(fmp_data, 'company_profile', 'mktCap', 0)
        tl = _safe_get(bs, ['Total Liab', 'Total Liabilities']) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalLiabilities', 0)
        sales = _safe_get(fs, ['Total Revenue', 'Revenue']) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', 0)

        if any(v is None or pd.isna(v) for v in [wc, ta, re, ebit, mve, tl, sales]):
            return {"error": "Missing non-calculable data for Z-Score."}
        if ta == 0 or tl == 0:
            return {"error": "Total Assets or Liabilities are zero, cannot calculate Z-Score."}
        
        A = wc / ta
        B = re / ta
        C = ebit / ta
        D = mve / tl
        E = sales / ta

        z_score = 1.2 * A + 1.4 * B + 3.3 * C + 0.6 * D + 1.0 * E
        return {"Altman Z-Score": z_score}

    except Exception as e:
        logger.error(f"Altman Z-Score calculation failed: {e}")
        return {"error": "An unexpected error occurred during Altman Z-Score calculation."}


def get_beneish_m_score(fs, bs, cf, fmp_data):
    """Calculates the Beneish M-Score for earnings manipulation risk."""
    try:
        if len(fs.columns) < 2 or len(bs.columns) < 2 or len(cf.columns) < 2:
            return {"error": "Not enough historical data for Beneish score."}

        # --- Data Extraction ---
        rec_y1 = _safe_get(bs, ['Accounts Receivable'], 0) or _safe_fmp_get(fmp_data, 'balance_sheet', 'netReceivables', 0)
        sales_y1 = _safe_get(fs, ['Total Revenue'], 0) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', 0)
        rec_y2 = _safe_get(bs, ['Accounts Receivable'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'netReceivables', 1)
        sales_y2 = _safe_get(fs, ['Total Revenue'], 1) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', 1)
        cogs_y1 = _safe_get(fs, ['Cost Of Revenue'], 0) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', 0)
        cogs_y2 = _safe_get(fs, ['Cost Of Revenue'], 1) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', 1)
        assets_y1 = _safe_get(bs, ['Total Assets'], 0) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', 0)
        assets_y2 = _safe_get(bs, ['Total Assets'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', 1)
        curr_assets_y1 = _safe_get(bs, ['Current Assets'], 0) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', 0)
        curr_assets_y2 = _safe_get(bs, ['Current Assets'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', 1)
        ppe_y1 = _safe_get(bs, ['Property Plant And Equipment', 'Net Property, Plant and Equipment'], 0) or _safe_fmp_get(fmp_data, 'balance_sheet', 'propertyPlantAndEquipmentNet', 0)
        ppe_y2 = _safe_get(bs, ['Property Plant And Equipment', 'Net Property, Plant and Equipment'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'propertyPlantAndEquipmentNet', 1)
        dep_y1 = _safe_get(cf, ['Depreciation And Amortization', 'Depreciation'], 0) or _safe_fmp_get(fmp_data, 'cash_flow', 'depreciationAndAmortization', 0)
        dep_y2 = _safe_get(cf, ['Depreciation And Amortization', 'Depreciation'], 1) or _safe_fmp_get(fmp_data, 'cash_flow', 'depreciationAndAmortization', 1)
        sga_y1 = _safe_get(fs, ['Selling General And Administration'], 0) or _safe_fmp_get(fmp_data, 'income_statement', 'sellingAndMarketingExpenses', 0)
        sga_y2 = _safe_get(fs, ['Selling General And Administration'], 1) or _safe_fmp_get(fmp_data, 'income_statement', 'sellingAndMarketingExpenses', 1)
        debt_y1 = _safe_get(bs, ['Total Debt'], 0) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', 0)
        debt_y2 = _safe_get(bs, ['Total Debt'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', 1)
        ni_y1 = _safe_get(fs, ['Net Income'], 0) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', 0)
        cfo_y1 = _safe_get(cf, ['Operating Cash Flow'], 0) or _safe_fmp_get(fmp_data, 'cash_flow', 'operatingCashFlow', 0)
        
        data_points = [rec_y1, sales_y1, rec_y2, sales_y2, cogs_y1, cogs_y2, assets_y1, assets_y2,
                       curr_assets_y1, curr_assets_y2, ppe_y1, ppe_y2, dep_y1, dep_y2,
                       sga_y1, sga_y2, debt_y1, debt_y2, ni_y1, cfo_y1]
        if any(pd.isna(v) for v in data_points):
            return {"error": "Missing critical data for Beneish Score."}

        dsri = (rec_y1 / sales_y1) / (rec_y2 / sales_y2) if sales_y1 and sales_y2 and sales_y1 != 0 and sales_y2 != 0 else 1.0
        gm_y1 = (sales_y1 - cogs_y1) / sales_y1 if sales_y1 and sales_y1 != 0 else 0
        gm_y2 = (sales_y2 - cogs_y2) / sales_y2 if sales_y2 and sales_y2 != 0 else 0
        gmi = gm_y2 / gm_y1 if gm_y1 and gm_y1 != 0 else 1.0
        aqi = (1 - ((curr_assets_y1 + ppe_y1) / assets_y1)) / (1 - ((curr_assets_y2 + ppe_y2) / assets_y2)) if assets_y1 and assets_y2 and assets_y1 != 0 and assets_y2 != 0 else 1.0
        sgi = sales_y1 / sales_y2 if sales_y2 and sales_y2 != 0 else 1.0
        depi = (dep_y2 / (ppe_y2 + dep_y2) if (ppe_y2 + dep_y2) != 0 else 0) / (dep_y1 / (ppe_y1 + dep_y1) if (ppe_y1 + dep_y1) != 0 else 1)
        sgai = (sga_y1 / sales_y1) / (sga_y2 / sales_y2) if sales_y1 and sales_y2 and sales_y1 != 0 and sales_y2 != 0 else 1.0
        lvgi = (debt_y1 / assets_y1) / (debt_y2 / assets_y2) if assets_y1 and assets_y2 and debt_y2 and assets_y1 != 0 and assets_y2 != 0 else 1.0
        tata = (ni_y1 - cfo_y1) / assets_y1 if assets_y1 and assets_y1 != 0 else 0.0

        m_score = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi +
                   0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)
        
        return {"Beneish M-Score": m_score}

    except Exception as e:
        logger.error(f"Beneish calculation failed: {e}")
        return {"error": "An unexpected error occurred during Beneish calculation."}


# --- Main Orchestrator Function (Refactored) ---
def analyze_fundamentals(ticker: str, basis: str = "annual"):
    """
    Orchestrates the 3-factor fundamental analysis model using the DataProvider.
    """
    try:
        # 1. Instantiate the provider. The complexity of data fetching is now hidden.
        provider = DataProvider(ticker)
    except ValueError as e:
        logger.error(f"Fundamental analysis failed for {ticker}: {e}")
        return {"error": str(e)}

    # 2. Get clean, simple data. No more need for the internal StockObject.
    financials, balance_sheet, cashflow = provider.get_financial_statements()
    info = provider.get_info()
    fmp_data = provider.get_fmp_data()

    # 3. Run the models with the clean data
    piotroski_result = get_piotroski_score(financials, balance_sheet, cashflow, info, fmp_data)
    altman_result = get_altman_z_score(financials, balance_sheet, info, fmp_data)
    beneish_result = get_beneish_m_score(financials, balance_sheet, cashflow, fmp_data)
    
    successful_scores = []
    breakdown = {}
    notes = []

    # 4. Process results (this logic remains largely the same)
    if "error" not in piotroski_result:
        f_raw = piotroski_result["Piotroski F-Score"]
        successful_scores.append((f_raw / 9) * 10)
        breakdown['Piotroski F-Score'] = f"{f_raw}/9"
    else:
        notes.append(f"Piotroski: {piotroski_result['error']}")
        breakdown['Piotroski F-Score'] = "N/A"

    if "error" not in altman_result:
        z_raw = altman_result["Altman Z-Score"]
        z_score_10 = min(max((z_raw - 1.8) / (2.99 - 1.8) * 10, 0.0), 10.0)
        successful_scores.append(z_score_10)
        breakdown['Altman Z-Score'] = f"{z_raw:.2f}"
        if z_raw > 2.99: breakdown['Bankruptcy Risk'] = "Safe"
        elif z_raw > 1.8: breakdown['Bankruptcy Risk'] = "Gray Zone"
        else: breakdown['Bankruptcy Risk'] = "Distress Zone"
    else:
        notes.append(f"Altman Z: {altman_result['error']}")
        breakdown['Altman Z-Score'] = "N/A"
        breakdown['Bankruptcy Risk'] = "N/A"

    if "error" not in beneish_result:
        m_raw = beneish_result["Beneish M-Score"]
        m_score_10 = min(max((-2.22 - m_raw) / 5 * 10, 0.0), 10.0)
        successful_scores.append(m_score_10)
        breakdown['Beneish M-Score'] = f"{m_raw:.2f}"
        breakdown['Manipulation Risk'] = "High" if m_raw > -2.22 else "Low"
    else:
        notes.append(f"Beneish: {beneish_result['error']}")
        breakdown['Beneish M-Score'] = "N/A"
        breakdown['Manipulation Risk'] = "N/A"

    if not successful_scores:
        final_score = 0
        verdict = "❌ Analysis Failed: All fundamental models failed due to missing data."
    else:
        final_score = (sum(successful_scores) / len(successful_scores)) * 10
        if final_score >= 80: verdict = "✅ Strong Value + Quality"
        elif final_score >= 65: verdict = "🟢 Fundamentally Sound"
        elif final_score >= 45: verdict = "🟡 Fair Value / Watchlist"
        else: verdict = "🔴 High Risk / Avoid"
    
    key_ratios = {
        "pe_ratio": info.get('trailingPE'),
        "pb_ratio": info.get('priceToBook'),
        "de_ratio": info.get('debtToEquity'),
        "roe": info.get('returnOnEquity'),
        "revenue_growth": info.get('revenueGrowth'),
        "free_cash_flow": info.get('freeCashflow')
    }

    return {
        "Fundamental Score": round(final_score, 2),
        "Verdict": verdict,
        "Notes": notes,
        "Breakdown": breakdown,
        **key_ratios
    }
