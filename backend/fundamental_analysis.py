# backend/fundamental_analysis.py
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)
from backend.data_fetcher import get_ticker_data

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
            value = df.loc[key].iloc[year]
            # Return the value itself if it's not NaN, otherwise continue the loop
            if pd.notna(value):
                return value
    return np.nan

# --- Sub-Score Calculation Functions with Intelligent Fallbacks ---

def get_piotroski_score(stock):
    """Calculates the 0-9 Piotroski F-Score with intelligent data fallbacks."""
    try:
        fs = stock.financials
        bs = stock.balance_sheet
        cf = stock.cashflow
        if len(fs.columns) < 2 or len(bs.columns) < 2 or len(cf.columns) < 2:
            # Attempt to use FMP data if Yahoo Finance is incomplete
            if not stock.fmp_data.get('income_statement') or len(stock.fmp_data['income_statement']) < 2:
                return {"error": "Not enough historical data for Piotroski score from any source."}

        # --- Intelligent Data Extraction with FMP Fallbacks ---
        fmp_income_y1 = stock.fmp_data.get('income_statement', [{}])[0]
        fmp_income_y2 = stock.fmp_data.get('income_statement', [{}, {}])[1]
        fmp_balance_y1 = stock.fmp_data.get('balance_sheet', [{}])[0]
        fmp_balance_y2 = stock.fmp_data.get('balance_sheet', [{}, {}])[1]
        fmp_cashflow_y1 = stock.fmp_data.get('cash_flow', [{}])[0]

        ni_y1 = _safe_get(fs, ['Net Income'], 0)
        if pd.isna(ni_y1): ni_y1 = fmp_income_y1.get('netIncome')
        
        assets_y1 = _safe_get(bs, ['Total Assets'], 0)
        if pd.isna(assets_y1): assets_y1 = fmp_balance_y1.get('totalAssets')
        
        roa_y1 = ni_y1 / assets_y1 if assets_y1 and ni_y1 is not None else 0

        ni_y2 = _safe_get(fs, ['Net Income'], 1)
        if pd.isna(ni_y2): ni_y2 = fmp_income_y2.get('netIncome')

        assets_y2 = _safe_get(bs, ['Total Assets'], 1)
        if pd.isna(assets_y2): assets_y2 = fmp_balance_y2.get('totalAssets')

        roa_y2 = ni_y2 / assets_y2 if assets_y2 and ni_y2 is not None else 0
        
        ocf_y1 = _safe_get(cf, ['Operating Cash Flow', 'Cash Flow from Operations'], 0)
        if pd.isna(ocf_y1): ocf_y1 = fmp_cashflow_y1.get('operatingCashFlow')

        rev_y1 = _safe_get(fs, ['Total Revenue'], 0)
        if pd.isna(rev_y1): rev_y1 = fmp_income_y1.get('revenue')
        
        gp_y1 = _safe_get(fs, ['Gross Profit'], 0)
        if pd.isna(gp_y1):
            cogs_y1 = _safe_get(fs, ['Cost Of Revenue'], 0)
            if pd.isna(cogs_y1): cogs_y1 = fmp_income_y1.get('costOfRevenue')
            gp_y1 = rev_y1 - cogs_y1 if rev_y1 is not None and cogs_y1 is not None else None
        gm_y1 = gp_y1 / rev_y1 if rev_y1 and gp_y1 is not None else 0

        rev_y2 = _safe_get(fs, ['Total Revenue'], 1)
        if pd.isna(rev_y2): rev_y2 = fmp_income_y2.get('revenue')

        gp_y2 = _safe_get(fs, ['Gross Profit'], 1)
        if pd.isna(gp_y2):
            cogs_y2 = _safe_get(fs, ['Cost Of Revenue'], 1)
            if pd.isna(cogs_y2): cogs_y2 = fmp_income_y2.get('costOfRevenue')
            gp_y2 = rev_y2 - cogs_y2 if rev_y2 is not None and cogs_y2 is not None else None
        gm_y2 = gp_y2 / rev_y2 if rev_y2 and gp_y2 is not None else 0
        
        debt_y1 = _safe_get(bs, ['Total Debt', 'Long Term Debt'], 0)
        if pd.isna(debt_y1): debt_y1 = fmp_balance_y1.get('totalDebt')

        debt_y2 = _safe_get(bs, ['Total Debt', 'Long Term Debt'], 1)
        if pd.isna(debt_y2): debt_y2 = fmp_balance_y2.get('totalDebt')

        curr_assets_y1 = _safe_get(bs, ['Current Assets'], 0)
        if pd.isna(curr_assets_y1): curr_assets_y1 = fmp_balance_y1.get('totalCurrentAssets')

        curr_liab_y1 = _safe_get(bs, ['Current Liabilities'], 0)
        if pd.isna(curr_liab_y1): curr_liab_y1 = fmp_balance_y1.get('totalCurrentLiabilities')

        cr_y1 = curr_assets_y1 / curr_liab_y1 if curr_liab_y1 and curr_assets_y1 is not None else 0

        curr_assets_y2 = _safe_get(bs, ['Current Assets'], 1)
        if pd.isna(curr_assets_y2): curr_assets_y2 = fmp_balance_y2.get('totalCurrentAssets')

        curr_liab_y2 = _safe_get(bs, ['Current Liabilities'], 1)
        if pd.isna(curr_liab_y2): curr_liab_y2 = fmp_balance_y2.get('totalCurrentLiabilities')

        cr_y2 = curr_assets_y2 / curr_liab_y2 if curr_liab_y2 and curr_assets_y2 is not None else 0
        
        shares_y1 = stock.info.get('sharesOutstanding')
        # Note: YF and FMP do not provide historical share counts easily. 
        # This is a known limitation. We assume shares outstanding are stable for this calculation.
        shares_y2 = shares_y1 

        data_points = [roa_y1, ocf_y1, debt_y1, debt_y2, cr_y1, cr_y2, shares_y1, shares_y2, gm_y1, gm_y2]
        if any(v is None or pd.isna(v) for v in data_points):
            return {"error": "Missing non-calculable critical data for Piotroski."}
            
        # Evaluate 9 signals
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
        logger.error(f"Piotroski calculation failed for {stock.ticker}: {e}")
        return {"error": "An unexpected error occurred during Piotroski calculation."}

def get_altman_z_score(stock):
    """Calculates the Altman Z-Score with intelligent data fallbacks."""
    try:
        sector = stock.info.get('sector', '')
        if 'Financial' in sector or 'Real Estate' in sector:
            return {"error": "Altman Z-Score not applicable to financial/real estate firms."}

        bs = stock.balance_sheet
        fs = stock.financials
        
        # --- Intelligent Data Extraction with Fallbacks (Prioritize FMP data) ---
        fmp_income = stock.fmp_data.get('income_statement', [{}])[0]
        fmp_balance = stock.fmp_data.get('balance_sheet', [{}])[0]
        fmp_metrics = stock.fmp_data.get('key_metrics', [{}])[0]
        fmp_profile = stock.fmp_data.get('company_profile', [{}])[0]

        ta = _safe_get(bs, ['Total Assets'])
        if pd.isna(ta):
            ta = fmp_balance.get('totalAssets')

        # Working Capital Fallback
        wc = _safe_get(bs, ['Working Capital'])
        if pd.isna(wc):
            logger.info(f"'{stock.ticker}': Missing 'Working Capital'. Calculating from Current Assets - Current Liabilities.")
            current_assets = _safe_get(bs, ['Current Assets'])
            current_liabilities = _safe_get(bs, ['Current Liabilities'])
            wc = current_assets - current_liabilities
        if pd.isna(wc):
            wc = fmp_balance.get('totalCurrentAssets') - fmp_balance.get('totalCurrentLiabilities')
            
        # Retained Earnings (no reliable fallback, get directly)
        re = _safe_get(bs, ['Retained Earnings'])
        if pd.isna(re):
            re = fmp_balance.get('retainedEarnings')
        
        # EBIT Fallback
        ebit = _safe_get(fs, ['EBIT', 'Operating Income'])
        if pd.isna(ebit):
            logger.info(f"'{stock.ticker}': Missing 'EBIT'. Calculating from Net Income + Interest + Taxes.")
            ni = _safe_get(fs, ['Net Income'])
            interest = _safe_get(fs, ['Interest Expense'], 0)
            taxes = _safe_get(fs, ['Tax Provision'], 0)
            ebit = ni + interest + taxes
        if pd.isna(ebit):
            ebit = fmp_income.get('ebitda') # FMP often provides EBITDA, which is close to EBIT for this purpose
            if pd.isna(ebit):
                ebit = fmp_income.get('operatingIncome')
            
        mve = stock.info.get('marketCap')
        if pd.isna(mve):
            mve = fmp_profile.get('mktCap')

        tl = _safe_get(bs, ['Total Liab', 'Total Liabilities'])
        if pd.isna(tl):
            tl = fmp_balance.get('totalLiabilities')

        sales = _safe_get(fs, ['Total Revenue', 'Revenue'])
        if pd.isna(sales):
            sales = fmp_income.get('revenue')

        if any(pd.isna(v) for v in [wc, ta, re, ebit, mve, tl, sales]):
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
        logger.error(f"Altman Z-Score calculation failed for {stock.ticker}: {e}")
        return {"error": "An unexpected error occurred during Altman Z-Score calculation."}

# In backend/fundamental_analysis.py

# --- REPLACE THE PLACEHOLDER BENEISH FUNCTION WITH THIS ---

def get_beneish_m_score(stock):
    """Calculates the Beneish M-Score for earnings manipulation risk."""
    try:
        fs = stock.financials
        bs = stock.balance_sheet
        cf = stock.cashflow
        if len(fs.columns) < 2 or len(bs.columns) < 2 or len(cf.columns) < 2:
            return {"error": "Not enough historical data for Beneish score."}

        # --- Safe Data Extraction for all 8 Beneish Indices (Prioritize FMP data) ---
        fmp_income = stock.fmp_data.get('income_statement', [{}])[0]
        fmp_balance = stock.fmp_data.get('balance_sheet', [{}])[0]
        fmp_cashflow = stock.fmp_data.get('cash_flow', [{}])[0]

        rec_y1 = _safe_get(bs, ['Accounts Receivable'], 0)
        if pd.isna(rec_y1):
            rec_y1 = fmp_balance.get('netReceivables')
        sales_y1 = _safe_get(fs, ['Total Revenue'], 0)
        if pd.isna(sales_y1):
            sales_y1 = fmp_income.get('revenue')

        rec_y2 = _safe_get(bs, ['Accounts Receivable'], 1)
        if pd.isna(rec_y2):
            rec_y2 = stock.fmp_data.get('balance_sheet', [{},{}])[1].get('netReceivables')
        sales_y2 = _safe_get(fs, ['Total Revenue'], 1)
        if pd.isna(sales_y2):
            sales_y2 = stock.fmp_data.get('income_statement', [{},{}])[1].get('revenue')

        cogs_y1 = _safe_get(fs, ['Cost Of Revenue'], 0)
        if pd.isna(cogs_y1):
            cogs_y1 = fmp_income.get('costOfRevenue')
        cogs_y2 = _safe_get(fs, ['Cost Of Revenue'], 1)
        if pd.isna(cogs_y2):
            cogs_y2 = stock.fmp_data.get('income_statement', [{},{}])[1].get('costOfRevenue')

        assets_y1 = _safe_get(bs, ['Total Assets'], 0)
        if pd.isna(assets_y1):
            assets_y1 = fmp_balance.get('totalAssets')
        assets_y2 = _safe_get(bs, ['Total Assets'], 1)
        if pd.isna(assets_y2):
            assets_y2 = stock.fmp_data.get('balance_sheet', [{},{}])[1].get('totalAssets')

        curr_assets_y1 = _safe_get(bs, ['Current Assets'], 0)
        if pd.isna(curr_assets_y1):
            curr_assets_y1 = fmp_balance.get('totalCurrentAssets')
        curr_assets_y2 = _safe_get(bs, ['Current Assets'], 1)
        if pd.isna(curr_assets_y2):
            curr_assets_y2 = stock.fmp_data.get('balance_sheet', [{},{}])[1].get('totalCurrentAssets')

        ppe_y1 = _safe_get(bs, ['Property Plant And Equipment', 'Net Property, Plant and Equipment'], 0)
        if pd.isna(ppe_y1):
            ppe_y1 = fmp_balance.get('propertyPlantAndEquipmentNet')
        ppe_y2 = _safe_get(bs, ['Property Plant And Equipment', 'Net Property, Plant and Equipment'], 1)
        if pd.isna(ppe_y2):
            ppe_y2 = stock.fmp_data.get('balance_sheet', [{},{}])[1].get('propertyPlantAndEquipmentNet')

        dep_y1 = _safe_get(cf, ['Depreciation And Amortization', 'Depreciation'], 0)
        if pd.isna(dep_y1):
            dep_y1 = fmp_cashflow.get('depreciationAndAmortization')
        dep_y2 = _safe_get(cf, ['Depreciation And Amortization', 'Depreciation'], 1)
        if pd.isna(dep_y2):
            dep_y2 = stock.fmp_data.get('cash_flow', [{},{}])[1].get('depreciationAndAmortization')

        sga_y1 = _safe_get(fs, ['Selling General And Administration'], 0)
        if pd.isna(sga_y1):
            sga_y1 = fmp_income.get('sellingAndMarketingExpenses') # FMP often combines SGA
            if pd.isna(sga_y1):
                sga_y1 = fmp_income.get('generalAndAdministrativeExpenses') + fmp_income.get('sellingExpenses') if fmp_income.get('generalAndAdministrativeExpenses') and fmp_income.get('sellingExpenses') else np.nan
        sga_y2 = _safe_get(fs, ['Selling General And Administration'], 1)
        if pd.isna(sga_y2):
            sga_y2 = stock.fmp_data.get('income_statement', [{},{}])[1].get('sellingAndMarketingExpenses')
            if pd.isna(sga_y2):
                sga_y2 = stock.fmp_data.get('income_statement', [{},{}])[1].get('generalAndAdministrativeExpenses') + stock.fmp_data.get('income_statement', [{},{}])[1].get('sellingExpenses') if stock.fmp_data.get('income_statement', [{},{}])[1].get('generalAndAdministrativeExpenses') and stock.fmp_data.get('income_statement', [{},{}])[1].get('sellingExpenses') else np.nan

        debt_y1 = _safe_get(bs, ['Total Debt'], 0)
        if pd.isna(debt_y1):
            debt_y1 = fmp_balance.get('totalDebt')
        debt_y2 = _safe_get(bs, ['Total Debt'], 1)
        if pd.isna(debt_y2):
            debt_y2 = stock.fmp_data.get('balance_sheet', [{},{}])[1].get('totalDebt')

        ni_y1 = _safe_get(fs, ['Net Income'], 0)
        if pd.isna(ni_y1):
            ni_y1 = fmp_income.get('netIncome')
        cfo_y1 = _safe_get(cf, ['Operating Cash Flow'], 0)
        if pd.isna(cfo_y1):
            cfo_y1 = fmp_cashflow.get('operatingCashFlow')
        
        # Check for missing data
        data_points = [rec_y1, sales_y1, rec_y2, sales_y2, cogs_y1, cogs_y2, assets_y1, assets_y2,
                       curr_assets_y1, curr_assets_y2, ppe_y1, ppe_y2, dep_y1, dep_y2,
                       sga_y1, sga_y2, debt_y1, debt_y2, ni_y1, cfo_y1]
        if any(pd.isna(v) for v in data_points):
            return {"error": "Missing critical data for Beneish Score."}

        # --- Calculate 8 Indices with Division-by-Zero checks ---
        dsri = (rec_y1 / sales_y1) / (rec_y2 / sales_y2) if sales_y1 and sales_y2 else 1.0
        gm_y1 = (sales_y1 - cogs_y1) / sales_y1 if sales_y1 else 0
        gm_y2 = (sales_y2 - cogs_y2) / sales_y2 if sales_y2 else 0
        gmi = gm_y2 / gm_y1 if gm_y1 else 1.0
        aqi = (1 - ((curr_assets_y1 + ppe_y1) / assets_y1)) / (1 - ((curr_assets_y2 + ppe_y2) / assets_y2)) if assets_y1 and assets_y2 else 1.0
        sgi = sales_y1 / sales_y2 if sales_y2 else 1.0
        depi = (dep_y2 / (ppe_y2 + dep_y2) if (ppe_y2 + dep_y2) else 0) / (dep_y1 / (ppe_y1 + dep_y1) if (ppe_y1 + dep_y1) else 1)
        sgai = (sga_y1 / sales_y1) / (sga_y2 / sales_y2) if sales_y1 and sales_y2 else 1.0
        lvgi = (debt_y1 / assets_y1) / (debt_y2 / assets_y2) if assets_y1 and assets_y2 and debt_y2 else 1.0
        tata = (ni_y1 - cfo_y1) / assets_y1 if assets_y1 else 0.0

        # Beneish M-Score Formula
        m_score = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi +
                   0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)
        
        return {"Beneish M-Score": m_score}

    except Exception as e:
        logger.error(f"Beneish calculation failed for {stock.ticker}: {e}")
        return {"error": "An unexpected error occurred during Beneish calculation."}


def analyze_fundamentals(ticker: str, basis: str = "annual"):
    """
    Orchestrates the 3-factor fundamental analysis model.
    """
    # Add this block to fetch data internally
    ticker_data = get_ticker_data(ticker)
    if "error" in ticker_data:
        return ticker_data  # Pass the error along if data fetching fails

    # Create a compatible "stock" object from the pre-fetched data dictionary
    class StockObject:
        def __init__(self, data):
            self.info = data.get("info", {})
            self.ticker = self.info.get("symbol", "N/A")
            # Convert split dictionaries back to DataFrames
            self.financials = pd.DataFrame(data['financials']['data'], columns=data['financials']['columns'], index=data['financials']['index']) if data.get("financials") else pd.DataFrame()
            self.balance_sheet = pd.DataFrame(data['balance_sheet']['data'], columns=data['balance_sheet']['columns'], index=data['balance_sheet']['index']) if data.get("balance_sheet") else pd.DataFrame()
            self.cashflow = pd.DataFrame(data['cashflow']['data'], columns=data['cashflow']['columns'], index=data['cashflow']['index']) if data.get("cashflow") else pd.DataFrame()
            self.fmp_data = data.get("fmp_data", {})

    stock = StockObject(ticker_data)

    successful_scores = []
    breakdown = {}
    notes = []

    # 1. Piotroski F-Score
    piotroski_result = get_piotroski_score(stock)
    if "error" in piotroski_result:
        notes.append(f"Piotroski: {piotroski_result['error']}")
        breakdown['Piotroski F-Score'] = "N/A"
    else:
        f_raw = piotroski_result["Piotroski F-Score"]
        successful_scores.append((f_raw / 9) * 10) # Add 0-10 score to list
        breakdown['Piotroski F-Score'] = f"{f_raw}/9"

    # 2. Altman Z-Score
    altman_result = get_altman_z_score(stock)
    if "error" in altman_result:
        notes.append(f"Altman Z: {altman_result['error']}")
        breakdown['Altman Z-Score'] = "N/A"
        breakdown['Risk'] = "N/A"
    else:
        z_raw = altman_result["Altman Z-Score"]
        z_score_10 = min(max((z_raw - 1.8) / (2.99 - 1.8) * 10, 0.0), 10.0)
        successful_scores.append(z_score_10) # Add 0-10 score to list
        breakdown['Altman Z-Score'] = f"{z_raw:.2f}"
        if z_raw > 2.99: breakdown['Risk'] = "Safe"
        elif z_raw > 1.8: breakdown['Risk'] = "Gray Zone"
        else: breakdown['Risk'] = "Distress Zone"

    # 3. Beneish M-Score
    beneish_result = get_beneish_m_score(stock)
    if "error" in beneish_result:
        notes.append(f"Beneish: {beneish_result['error']}")
        breakdown['Beneish M-Score'] = "N/A"
        breakdown['Risk'] = "N/A"
    else:
        m_raw = beneish_result["Beneish M-Score"]
        m_score_10 = min(max((-2.22 - m_raw) / 5 * 10, 0.0), 10.0)
        successful_scores.append(m_score_10) # Add 0-10 score to list
        breakdown['Beneish M-Score'] = f"{m_raw:.2f}"
        breakdown['Risk'] = "High" if m_raw > -2.22 else "Low"

    # --- Final Composite Score and Verdict ---
    if not successful_scores:
        # Handle case where all models fail
        final_score = 0
        verdict = "❌ Analysis Failed: All fundamental models failed due to missing data."
        notes.append("All fundamental models failed due to missing data.")
    else:
        # Average only the scores from the models that succeeded
        final_score = (sum(successful_scores) / len(successful_scores)) * 10
        if final_score >= 90:
            verdict = "🌟 Exceptional Value: Outstanding fundamentals and quality."
        elif final_score >= 80:
            verdict = "✅ Strong Value + Quality: Very robust fundamentals."
        elif final_score >= 65:
            verdict = "🟢 Fundamentally Sound: Good value and quality."
        elif final_score >= 45:
            verdict = "🟡 Fair Value / Watchlist: Average fundamentals, monitor closely."
        elif final_score >= 25:
            verdict = "🟠 Elevated Risk: Weak fundamentals, exercise caution."
        else:
            verdict = "🔴 High Risk / Avoid: Poor fundamentals, significant risk."
    
    # --- Extract additional key ratios for screener/strategies ---
    info = stock.info
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
        "Breakdown": breakdown
    }