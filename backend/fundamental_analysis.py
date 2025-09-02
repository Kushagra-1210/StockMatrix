import pandas as pd
import numpy as np
import logging
from backend.data_provider import DataProvider

logger = logging.getLogger(__name__)

# --- Helper functions to safely access financial data ---
def _safe_get(df, keys, year=0):
    """Safely gets a value from a DataFrame by trying multiple possible keys for a given year index."""
    if df is None or df.empty or year >= len(df.columns):
        return np.nan
    for key in keys:
        if key in df.index:
            try:
                value = df.loc[key].iloc[year]
                if pd.notna(value):
                    return value
            except IndexError:
                # This can happen if a row exists but has fewer columns than expected
                continue
    return np.nan

def _safe_fmp_get(fmp_data_dict, statement_type, key, year=0):
    """Safely gets a value from the FMP fallback data dictionary."""
    statement = fmp_data_dict.get(statement_type)
    if statement and isinstance(statement, list) and len(statement) > year:
        if isinstance(statement[year], dict):
            return statement[year].get(key)
    return np.nan

# --- Sub-Score Calculation Functions with Historical Fallback ---

def get_piotroski_score(fs, bs, cf, info, fmp_data):
    """Calculates the Piotroski F-Score, falling back to the previous period if current data is incomplete."""
    notes = []
    for year_idx in range(2): # Try current year (0), then previous year (1)
        try:
            # Year 1 (Current or T-1)
            ni_y1 = _safe_get(fs, ['Net Income'], year_idx) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', year_idx)
            assets_y1 = _safe_get(bs, ['Total Assets'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', year_idx)
            roa_y1 = ni_y1 / assets_y1 if assets_y1 and ni_y1 is not None else 0
            ocf_y1 = _safe_get(cf, ['Operating Cash Flow', 'Cash Flow from Operations'], year_idx) or _safe_fmp_get(fmp_data, 'cash_flow', 'operatingCashFlow', year_idx)
            rev_y1 = _safe_get(fs, ['Total Revenue'], year_idx) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', year_idx)
            cogs_y1 = _safe_get(fs, ['Cost Of Revenue'], year_idx) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', year_idx)
            gp_y1 = rev_y1 - cogs_y1 if rev_y1 is not None and cogs_y1 is not None else _safe_get(fs, ['Gross Profit'], year_idx)
            gm_y1 = gp_y1 / rev_y1 if rev_y1 and gp_y1 is not None else 0
            debt_y1 = _safe_get(bs, ['Total Debt', 'Long Term Debt'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', year_idx)
            curr_assets_y1 = _safe_get(bs, ['Current Assets'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', year_idx)
            curr_liab_y1 = _safe_get(bs, ['Current Liabilities'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', year_idx)
            cr_y1 = curr_assets_y1 / curr_liab_y1 if curr_liab_y1 and curr_assets_y1 is not None else 0
            shares_y1 = info.get('sharesOutstanding')

            # Year 2 (T-1 or T-2)
            ni_y2 = _safe_get(fs, ['Net Income'], year_idx + 1) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', year_idx + 1)
            assets_y2 = _safe_get(bs, ['Total Assets'], year_idx + 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', year_idx + 1)
            roa_y2 = ni_y2 / assets_y2 if assets_y2 and ni_y2 is not None else 0
            rev_y2 = _safe_get(fs, ['Total Revenue'], year_idx + 1) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', year_idx + 1)
            cogs_y2 = _safe_get(fs, ['Cost Of Revenue'], year_idx + 1) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', year_idx + 1)
            gp_y2 = rev_y2 - cogs_y2 if rev_y2 is not None and cogs_y2 is not None else _safe_get(fs, ['Gross Profit'], year_idx + 1)
            gm_y2 = gp_y2 / rev_y2 if rev_y2 and gp_y2 is not None else 0
            debt_y2 = _safe_get(bs, ['Total Debt', 'Long Term Debt'], year_idx + 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', year_idx + 1)
            curr_assets_y2 = _safe_get(bs, ['Current Assets'], year_idx + 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', year_idx + 1)
            curr_liab_y2 = _safe_get(bs, ['Current Liabilities'], year_idx + 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', year_idx + 1)
            cr_y2 = curr_assets_y2 / curr_liab_y2 if curr_liab_y2 and curr_assets_y2 is not None else 0
            shares_y2 = shares_y1 # Assume no change for simplicity in this model
            
            data_points = [roa_y1, ocf_y1, debt_y1, debt_y2, cr_y1, cr_y2, shares_y1, shares_y2, gm_y1, gm_y2, roa_y2]
            if any(v is None or pd.isna(v) for v in data_points):
                if year_idx == 0:
                    notes.append("Piotroski: Current data incomplete, attempting fallback.")
                    continue
                else:
                    return {"error": "Missing critical data for Piotroski score in both periods."}

            f_roa = 1 if roa_y1 > 0 else 0
            f_ocf = 1 if ocf_y1 > 0 else 0
            f_delta_roa = 1 if roa_y1 > roa_y2 else 0
            f_cfo_roa = 1 if ocf_y1 > ni_y1 else 0
            f_delta_lev = 1 if (debt_y1 / assets_y1 if assets_y1 else float('inf')) <= (debt_y2 / assets_y2 if assets_y2 else float('inf')) else 0
            f_delta_cr = 1 if cr_y1 > cr_y2 else 0
            f_shares = 1 if shares_y1 <= shares_y2 else 0
            f_delta_gm = 1 if gm_y1 > gm_y2 else 0
            at_y1 = rev_y1 / assets_y1 if assets_y1 else 0
            at_y2 = rev_y2 / assets_y2 if assets_y2 else 0
            f_delta_at = 1 if at_y1 > at_y2 else 0
            
            f_score = sum([f_roa, f_ocf, f_cfo_roa, f_delta_roa, f_delta_lev, f_delta_cr, f_shares, f_delta_gm, f_delta_at])
            
            if year_idx > 0:
                notes.append("Piotroski: Used last available complete data (Previous Period).")

            return {"Piotroski F-Score": f_score, "notes": notes}
        except (TypeError, IndexError, ValueError):
             if year_idx == 0:
                notes.append("Piotroski: Data format error, attempting fallback.")
                continue
             else:
                return {"error": "Data format error prevented Piotroski calculation."}
    
    return {"error": "Could not calculate Piotroski Score after all fallbacks."}

def get_altman_z_score(fs, bs, info, fmp_data):
    """Calculates the Altman Z-Score, falling back to the previous period if current data is incomplete."""
    notes = []
    for year_idx in range(2):
        try:
            ta = _safe_get(bs, ['Total Assets'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', year_idx)
            wc = _safe_get(bs, ['Working Capital'], year_idx)
            if pd.isna(wc):
                current_assets = _safe_get(bs, ['Current Assets'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', year_idx)
                current_liabilities = _safe_get(bs, ['Current Liabilities'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', year_idx)
                if pd.notna(current_assets) and pd.notna(current_liabilities):
                    wc = current_assets - current_liabilities
            
            re = _safe_get(bs, ['Retained Earnings'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'retainedEarnings', year_idx)
            ebit = _safe_get(fs, ['EBIT', 'Operating Income'], year_idx) or _safe_fmp_get(fmp_data, 'income_statement', 'operatingIncome', year_idx)
            mve = info.get('marketCap')
            tl = _safe_get(bs, ['Total Liab', 'Total Liabilities'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalLiabilities', year_idx)
            sales = _safe_get(fs, ['Total Revenue', 'Revenue'], year_idx) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', year_idx)

            required_vars = [wc, ta, re, ebit, mve, tl, sales]
            if any(v is None or pd.isna(v) for v in required_vars):
                if year_idx == 0:
                    notes.append("Altman Z: Current data incomplete, attempting fallback.")
                    continue
                else:
                    return {"error": "Missing critical data for Z-Score in both periods."}
            
            if ta == 0 or tl == 0:
                return {"error": "Total Assets or Liabilities are zero."}

            A, B, C, D, E = (wc / ta), (re / ta), (ebit / ta), (mve / tl), (sales / ta)
            z_score = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E
            
            if year_idx > 0:
                notes.append("Altman Z: Used last available complete data (Previous Period).")

            return {"Altman Z-Score": z_score, "notes": notes}
        except (TypeError, IndexError, ValueError):
            if year_idx == 0:
                notes.append("Altman Z: Data format error, attempting fallback.")
                continue
            else:
                return {"error": "Data format error prevented Z-Score calculation."}
    
    return {"error": "Could not calculate Z-Score after all fallbacks."}

def get_beneish_m_score(fs, bs, cf, fmp_data):
    """Calculates the Beneish M-Score, falling back to the previous period."""
    notes = []
    for year_idx in range(2):
        try:
            # Year 1 data
            rec_y1 = _safe_get(bs, ['Accounts Receivable', 'Net Receivables'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'netReceivables', year_idx)
            sales_y1 = _safe_get(fs, ['Total Revenue'], year_idx) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', year_idx)
            cogs_y1 = _safe_get(fs, ['Cost Of Revenue'], year_idx) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', year_idx)
            assets_y1 = _safe_get(bs, ['Total Assets'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', year_idx)
            curr_assets_y1 = _safe_get(bs, ['Current Assets'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', year_idx)
            ppe_y1 = _safe_get(bs, ['Property Plant And Equipment', 'Property Plant And Equipment Net'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'propertyPlantAndEquipmentNet', year_idx)
            dep_y1 = _safe_get(cf, ['Depreciation And Amortization'], year_idx) or _safe_fmp_get(fmp_data, 'cash_flow', 'depreciationAndAmortization', year_idx)
            sga_y1 = _safe_get(fs, ['Selling General And Administration', 'Selling General And Administrative Expenses'], year_idx) or _safe_fmp_get(fmp_data, 'income_statement', 'sellingGeneralAndAdministrativeExpenses', year_idx)
            debt_y1 = _safe_get(bs, ['Total Debt'], year_idx) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', year_idx)
            ni_y1 = _safe_get(fs, ['Net Income'], year_idx) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', year_idx)
            cfo_y1 = _safe_get(cf, ['Operating Cash Flow'], year_idx) or _safe_fmp_get(fmp_data, 'cash_flow', 'operatingCashFlow', year_idx)
            
            # Year 2 data
            rec_y2 = _safe_get(bs, ['Accounts Receivable', 'Net Receivables'], year_idx + 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'netReceivables', year_idx + 1)
            sales_y2 = _safe_get(fs, ['Total Revenue'], year_idx + 1) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', year_idx + 1)
            cogs_y2 = _safe_get(fs, ['Cost Of Revenue'], year_idx + 1) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', year_idx + 1)
            assets_y2 = _safe_get(bs, ['Total Assets'], year_idx + 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', year_idx + 1)
            curr_assets_y2 = _safe_get(bs, ['Current Assets'], year_idx + 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', year_idx + 1)
            ppe_y2 = _safe_get(bs, ['Property Plant And Equipment', 'Property Plant And Equipment Net'], year_idx + 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'propertyPlantAndEquipmentNet', year_idx + 1)
            dep_y2 = _safe_get(cf, ['Depreciation And Amortization'], year_idx + 1) or _safe_fmp_get(fmp_data, 'cash_flow', 'depreciationAndAmortization', year_idx + 1)
            sga_y2 = _safe_get(fs, ['Selling General And Administration', 'Selling General And Administrative Expenses'], year_idx + 1) or _safe_fmp_get(fmp_data, 'income_statement', 'sellingGeneralAndAdministrativeExpenses', year_idx + 1)
            debt_y2 = _safe_get(bs, ['Total Debt'], year_idx + 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', year_idx + 1)

            data_points = [rec_y1, sales_y1, assets_y1, rec_y2, sales_y2, assets_y2, cogs_y1, cogs_y2,
                           curr_assets_y1, ppe_y1, curr_assets_y2, ppe_y2, dep_y1, sga_y1, debt_y1, ni_y1, cfo_y1,
                           dep_y2, sga_y2, debt_y2]
                           
            if any(pd.isna(v) for v in data_points):
                if year_idx == 0:
                    notes.append("Beneish: Current data incomplete, attempting fallback.")
                    continue
                else:
                    return {"error": "Missing critical data for Beneish Score in both periods."}

            dsri = (rec_y1 / sales_y1) / (rec_y2 / sales_y2) if sales_y1 and sales_y2 else 1.0
            gmi = ((sales_y2 - cogs_y2) / sales_y2) / ((sales_y1 - cogs_y1) / sales_y1) if sales_y1 and sales_y2 else 1.0
            aqi = (1 - (curr_assets_y1 + ppe_y1) / assets_y1) / (1 - (curr_assets_y2 + ppe_y2) / assets_y2) if assets_y1 and assets_y2 else 1.0
            sgi = sales_y1 / sales_y2 if sales_y2 else 1.0
            depi = (dep_y2 / (dep_y2 + ppe_y2 if ppe_y2 else 0)) / (dep_y1 / (dep_y1 + ppe_y1 if ppe_y1 else 0)) if dep_y1 and (dep_y1 + ppe_y1) and (dep_y2 + ppe_y2) else 1.0
            sgai = (sga_y1 / sales_y1) / (sga_y2 / sales_y2) if sales_y1 and sales_y2 else 1.0
            lvgi = (debt_y1 / assets_y1) / (debt_y2 / assets_y2) if assets_y1 and assets_y2 else 1.0
            tata = (ni_y1 - cfo_y1) / assets_y1 if assets_y1 else 0.0

            m_score = -4.84 + 0.92*dsri + 0.528*gmi + 0.404*aqi + 0.892*sgi + 0.115*depi - 0.172*sgai + 4.679*tata - 0.327*lvgi
            
            if year_idx > 0:
                notes.append("Beneish: Used last available complete data (Previous Period).")

            return {"Beneish M-Score": m_score, "notes": notes}
        except (TypeError, IndexError, ValueError):
            if year_idx == 0:
                notes.append("Beneish: Data format error, attempting fallback.")
                continue
            else:
                return {"error": "Data format error prevented Beneish calculation."}
    
    return {"error": "Could not calculate Beneish Score after all fallbacks."}

# --- Main Orchestrator Function ---
def analyze_fundamentals(ticker: str, basis: str = "annual"):
    """Orchestrates the fundamental analysis, gathering results and notes from each model."""
    try:
        provider = DataProvider(ticker)
    except ValueError as e:
        logger.error(f"Fundamental analysis failed for {ticker}: {e}")
        return {"error": str(e)}

    financials, balance_sheet, cashflow = provider.get_financial_statements()
    info = provider.get_info()
    fmp_data = provider.get_fmp_data()
    
    piotroski_result = get_piotroski_score(financials, balance_sheet, cashflow, info, fmp_data)
    altman_result = get_altman_z_score(financials, balance_sheet, info, fmp_data)
    beneish_result = get_beneish_m_score(financials, balance_sheet, cashflow, fmp_data)
    
    successful_scores = []
    breakdown = {}
    notes = []

    # Process Piotroski
    if "error" not in piotroski_result:
        f_raw = piotroski_result["Piotroski F-Score"]
        successful_scores.append((f_raw / 9) * 10)
        breakdown['Piotroski F-Score'] = f"{f_raw}/9"
        if "notes" in piotroski_result: notes.extend(piotroski_result["notes"])
    else:
        notes.append(f"Piotroski: {piotroski_result['error']}")
        breakdown['Piotroski F-Score'] = "N/A"

    # Process Altman
    if "error" not in altman_result:
        z_raw = altman_result["Altman Z-Score"]
        z_score_10 = min(max((z_raw - 1.8) / (2.99 - 1.8) * 10, 0.0), 10.0)
        successful_scores.append(z_score_10)
        breakdown['Altman Z-Score'] = f"{z_raw:.2f}"
        if z_raw > 2.99: breakdown['Bankruptcy Risk'] = "Safe"
        elif z_raw > 1.8: breakdown['Bankruptcy Risk'] = "Gray Zone"
        else: breakdown['Bankruptcy Risk'] = "Distress Zone"
        if "notes" in altman_result: notes.extend(altman_result["notes"])
    else:
        notes.append(f"Altman Z: {altman_result['error']}")
        breakdown['Altman Z-Score'] = "N/A"
        breakdown['Bankruptcy Risk'] = "N/A"

    # Process Beneish
    if "error" not in beneish_result:
        m_raw = beneish_result["Beneish M-Score"]
        m_score_10 = min(max((-2.22 - m_raw) / 5 * 10, 0.0), 10.0)
        successful_scores.append(m_score_10)
        breakdown['Beneish M-Score'] = f"{m_raw:.2f}"
        breakdown['Manipulation Risk'] = "High" if m_raw > -2.22 else "Low"
        if "notes" in beneish_result: notes.extend(beneish_result["notes"])
    else:
        notes.append(f"Beneish: {beneish_result['error']}")
        breakdown['Beneish M-Score'] = "N/A"
        breakdown['Manipulation Risk'] = "N/A"

    if not successful_scores:
        final_score = 0
        verdict = "❌ Analysis Failed"
        notes.append("All fundamental models failed due to missing data.")
    else:
        final_score = (sum(successful_scores) / len(successful_scores)) * 10
        if final_score >= 80: verdict = "✅ Strong Value + Quality"
        elif final_score >= 65: verdict = "🟢 Fundamentally Sound"
        elif final_score >= 45: verdict = "🟡 Fair Value / Watchlist"
        else: verdict = "🔴 High Risk / Avoid"
    
    return {
        "Fundamental Score": round(final_score, 2),
        "Verdict": verdict,
        "Notes": list(set(notes)), # Remove duplicate notes
        "Breakdown": breakdown
    }

