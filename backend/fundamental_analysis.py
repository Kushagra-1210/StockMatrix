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

        def get_fields(year=0):
            ni = _safe_get(fs, ['Net Income'], year) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', year)
            assets = _safe_get(bs, ['Total Assets'], year) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', year)
            roa = ni / assets if assets and ni is not None else 0

            ocf = _safe_get(cf, ['Operating Cash Flow', 'Cash Flow from Operations'], year) or _safe_fmp_get(fmp_data, 'cash_flow', 'operatingCashFlow', year)
            rev = _safe_get(fs, ['Total Revenue'], year) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', year)
            cogs = _safe_get(fs, ['Cost Of Revenue'], year) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', year)
            gp = rev - cogs if rev is not None and cogs is not None else _safe_get(fs, ['Gross Profit'], year)
            gm = gp / rev if rev and gp is not None else 0

            debt = _safe_get(bs, ['Total Debt', 'Long Term Debt'], year) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', year)
            curr_assets = _safe_get(bs, ['Current Assets'], year) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', year)
            curr_liab = _safe_get(bs, ['Current Liabilities'], year) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', year)
            cr = curr_assets / curr_liab if curr_liab and curr_assets is not None else 0

            shares = info.get('sharesOutstanding')

            fields = {
                'roa': roa,
                'ocf': ocf,
                'debt': debt,
                'cr': cr,
                'shares': shares,
                'gm': gm,
                'rev': rev,
                'assets': assets
            }
            return fields

        # Try current period (year=0)
        f = get_fields(year=0)
        f2 = get_fields(year=1)
        data_points = [f['roa'], f['ocf'], f['debt'], f['cr'], f['shares'], f['gm'], f['rev'], f['assets']]
        if not any(v is None or pd.isna(v) for v in data_points):
            # Use year=0 and year=1 for delta calculations
            f2 = get_fields(year=1)
            ni_y2 = _safe_get(fs, ['Net Income'], 1) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', 1)
            assets_y2 = _safe_get(bs, ['Total Assets'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', 1)
            roa_y2 = ni_y2 / assets_y2 if assets_y2 and ni_y2 is not None else 0
            debt_y2 = _safe_get(bs, ['Total Debt', 'Long Term Debt'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', 1)
            cr_y2 = _safe_get(bs, ['Current Assets'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', 1)
            cr_liab_y2 = _safe_get(bs, ['Current Liabilities'], 1) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', 1)
            cr_y2 = cr_y2 / cr_liab_y2 if cr_liab_y2 and cr_y2 is not None else 0
            rev_y2 = _safe_get(fs, ['Total Revenue'], 1) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', 1)
            cogs_y2 = _safe_get(fs, ['Cost Of Revenue'], 1) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', 1)
            gp_y2 = rev_y2 - cogs_y2 if rev_y2 is not None and cogs_y2 is not None else _safe_get(fs, ['Gross Profit'], 1)
            gm_y2 = gp_y2 / rev_y2 if rev_y2 and gp_y2 is not None else 0
            shares_y2 = info.get('sharesOutstanding')
            f_roa = 1 if f['roa'] > 0 else 0
            f_ocf = 1 if f['ocf'] > 0 else 0
            f_cfo_roa = 1 if f['ocf'] > f['roa'] else 0
            f_delta_roa = 1 if f['roa'] > roa_y2 else 0
            f_delta_lev = 1 if (f['debt'] / f['assets'] if f['assets'] else 0) < (debt_y2 / assets_y2 if assets_y2 else 0) else 0
            f_delta_cr = 1 if f['cr'] > cr_y2 else 0
            f_shares = 1 if f['shares'] <= shares_y2 else 0
            f_delta_gm = 1 if f['gm'] > gm_y2 else 0
            at_y1 = f['rev'] / f['assets'] if f['assets'] else 0
            at_y2 = rev_y2 / assets_y2 if assets_y2 else 0
            f_delta_at = 1 if at_y1 > at_y2 else 0
            f_score = sum([f_roa, f_ocf, f_cfo_roa, f_delta_roa, f_delta_lev, f_delta_cr, f_shares, f_delta_gm, f_delta_at])
            return {"Piotroski F-Score": f_score}
        # If missing, try previous period (year=1)
        data_points_prev = [f2['roa'], f2['ocf'], f2['debt'], f2['cr'], f2['shares'], f2['gm'], f2['rev'], f2['assets']]
        if not any(v is None or pd.isna(v) for v in data_points_prev):
            # Use year=1 and year=2 for delta calculations
            f3 = get_fields(year=2)
            ni_y3 = _safe_get(fs, ['Net Income'], 2) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', 2)
            assets_y3 = _safe_get(bs, ['Total Assets'], 2) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', 2)
            roa_y3 = ni_y3 / assets_y3 if assets_y3 and ni_y3 is not None else 0
            debt_y3 = _safe_get(bs, ['Total Debt', 'Long Term Debt'], 2) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', 2)
            cr_y3 = _safe_get(bs, ['Current Assets'], 2) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', 2)
            cr_liab_y3 = _safe_get(bs, ['Current Liabilities'], 2) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', 2)
            cr_y3 = cr_y3 / cr_liab_y3 if cr_liab_y3 and cr_y3 is not None else 0
            rev_y3 = _safe_get(fs, ['Total Revenue'], 2) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', 2)
            cogs_y3 = _safe_get(fs, ['Cost Of Revenue'], 2) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', 2)
            gp_y3 = rev_y3 - cogs_y3 if rev_y3 is not None and cogs_y3 is not None else _safe_get(fs, ['Gross Profit'], 2)
            gm_y3 = gp_y3 / rev_y3 if rev_y3 and gp_y3 is not None else 0
            shares_y3 = info.get('sharesOutstanding')
            f_roa = 1 if f2['roa'] > 0 else 0
            f_ocf = 1 if f2['ocf'] > 0 else 0
            f_cfo_roa = 1 if f2['ocf'] > f2['roa'] else 0
            f_delta_roa = 1 if f2['roa'] > roa_y3 else 0
            f_delta_lev = 1 if (f2['debt'] / f2['assets'] if f2['assets'] else 0) < (debt_y3 / assets_y3 if assets_y3 else 0) else 0
            f_delta_cr = 1 if f2['cr'] > cr_y3 else 0
            f_shares = 1 if f2['shares'] <= shares_y3 else 0
            f_delta_gm = 1 if f2['gm'] > gm_y3 else 0
            at_y1 = f2['rev'] / f2['assets'] if f2['assets'] else 0
            at_y2 = rev_y3 / assets_y3 if assets_y3 else 0
            f_delta_at = 1 if at_y1 > at_y2 else 0
            f_score = sum([f_roa, f_ocf, f_cfo_roa, f_delta_roa, f_delta_lev, f_delta_cr, f_shares, f_delta_gm, f_delta_at])
            note = "Used last available complete data (Previous Period)."
            return {"Piotroski F-Score": f_score, "note": note}
        return {"error": "Missing non-calculable critical data for Piotroski."}

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


        def get_fields(year=0):
            ta = _safe_get(bs, ['Total Assets'], year)
            ta_fmp = False
            if pd.isna(ta):
                ta = _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', year)
                ta_fmp = True

            wc = _safe_get(bs, ['Working Capital'], year)
            wc_fmp = False
            if pd.isna(wc):
                current_assets = _safe_get(bs, ['Current Assets'], year)
                ca_fmp = False
                if pd.isna(current_assets):
                    current_assets = _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', year)
                    ca_fmp = True
                current_liabilities = _safe_get(bs, ['Current Liabilities'], year)
                cl_fmp = False
                if pd.isna(current_liabilities):
                    current_liabilities = _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', year)
                    cl_fmp = True
                wc = current_assets - current_liabilities
                wc_fmp = ca_fmp or cl_fmp

            re = _safe_get(bs, ['Retained Earnings'], year)
            re_fmp = False
            if pd.isna(re):
                re = _safe_fmp_get(fmp_data, 'balance_sheet', 'retainedEarnings', year)
                re_fmp = True

            ebit = _safe_get(fs, ['EBIT', 'Operating Income'], year)
            ebit_fmp = False
            if pd.isna(ebit):
                ni = _safe_get(fs, ['Net Income'], year)
                interest = _safe_get(fs, ['Interest Expense'], year)
                taxes = _safe_get(fs, ['Tax Provision'], year)
                if all(pd.notna([ni, interest, taxes])):
                    ebit = ni + interest + taxes
                else:
                    ebit = _safe_fmp_get(fmp_data, 'income_statement', 'operatingIncome', year)
                    ebit_fmp = True

            mve = info.get('marketCap')
            mve_fmp = False
            if mve is None or pd.isna(mve):
                mve = _safe_fmp_get(fmp_data, 'company_profile', 'mktCap', 0)
                mve_fmp = True

            tl = _safe_get(bs, ['Total Liab', 'Total Liabilities'], year)
            tl_fmp = False
            if pd.isna(tl):
                tl = _safe_fmp_get(fmp_data, 'balance_sheet', 'totalLiabilities', year)
                tl_fmp = True

            sales = _safe_get(fs, ['Total Revenue', 'Revenue'], year)
            sales_fmp = False
            if pd.isna(sales):
                sales = _safe_fmp_get(fmp_data, 'income_statement', 'revenue', year)
                sales_fmp = True

            fields = {
                'Working Capital': wc,
                'Total Assets': ta,
                'Retained Earnings': re,
                'EBIT': ebit,
                'Market Value of Equity': mve,
                'Total Liabilities': tl,
                'Sales': sales
            }
            fmp_used = [k for k, used in zip(fields.keys(), [wc_fmp, ta_fmp, re_fmp, ebit_fmp, mve_fmp, tl_fmp, sales_fmp]) if used]
            return fields, fmp_used

        # Try current period (year=0)
        fields, fmp_used = get_fields(year=0)
        missing = [k for k, v in fields.items() if v is None or pd.isna(v)]
        if not missing and fields['Total Assets'] != 0 and fields['Total Liabilities'] != 0:
            A = fields['Working Capital'] / fields['Total Assets']
            B = fields['Retained Earnings'] / fields['Total Assets']
            C = fields['EBIT'] / fields['Total Assets']
            D = fields['Market Value of Equity'] / fields['Total Liabilities']
            E = fields['Sales'] / fields['Total Assets']
            z_score = 1.2 * A + 1.4 * B + 3.3 * C + 0.6 * D + 1.0 * E
            return {"Altman Z-Score": z_score}
        # If missing, try previous period (year=1)
        fields_prev, fmp_used_prev = get_fields(year=1)
        missing_prev = [k for k, v in fields_prev.items() if v is None or pd.isna(v)]
        if not missing_prev and fields_prev['Total Assets'] != 0 and fields_prev['Total Liabilities'] != 0:
            A = fields_prev['Working Capital'] / fields_prev['Total Assets']
            B = fields_prev['Retained Earnings'] / fields_prev['Total Assets']
            C = fields_prev['EBIT'] / fields_prev['Total Assets']
            D = fields_prev['Market Value of Equity'] / fields_prev['Total Liabilities']
            E = fields_prev['Sales'] / fields_prev['Total Assets']
            z_score = 1.2 * A + 1.4 * B + 3.3 * C + 0.6 * D + 1.0 * E
            note = "Used last available complete data (Previous Period)."
            return {"Altman Z-Score": z_score, "note": note}
        # If still missing, report missing fields
        msg = f"Missing non-calculable data for Z-Score. Missing fields: {', '.join(missing)}. "
        if fmp_used:
            msg += f"FMP fallback used for: {', '.join(fmp_used)}. "
        return {"error": msg.strip()}

    except Exception as e:
        logger.error(f"Altman Z-Score calculation failed: {e}")
        return {"error": "An unexpected error occurred during Altman Z-Score calculation."}


def get_beneish_m_score(fs, bs, cf, fmp_data):
    """Calculates the Beneish M-Score for earnings manipulation risk."""
    try:
        if len(fs.columns) < 2 or len(bs.columns) < 2 or len(cf.columns) < 2:
            return {"error": "Not enough historical data for Beneish score."}

        def get_fields(year=0):
            rec = _safe_get(bs, ['Accounts Receivable'], year) or _safe_fmp_get(fmp_data, 'balance_sheet', 'netReceivables', year)
            sales = _safe_get(fs, ['Total Revenue'], year) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', year)
            cogs = _safe_get(fs, ['Cost Of Revenue'], year) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', year)
            assets = _safe_get(bs, ['Total Assets'], year) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', year)
            curr_assets = _safe_get(bs, ['Current Assets'], year) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', year)
            ppe = _safe_get(bs, ['Property Plant And Equipment', 'Net Property, Plant and Equipment'], year) or _safe_fmp_get(fmp_data, 'balance_sheet', 'propertyPlantAndEquipmentNet', year)
            dep = _safe_get(cf, ['Depreciation And Amortization', 'Depreciation'], year) or _safe_fmp_get(fmp_data, 'cash_flow', 'depreciationAndAmortization', year)
            sga = _safe_get(fs, ['Selling General And Administration'], year) or _safe_fmp_get(fmp_data, 'income_statement', 'sellingAndMarketingExpenses', year)
            debt = _safe_get(bs, ['Total Debt'], year) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', year)
            ni = _safe_get(fs, ['Net Income'], year) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', year)
            cfo = _safe_get(cf, ['Operating Cash Flow'], year) or _safe_fmp_get(fmp_data, 'cash_flow', 'operatingCashFlow', year)
            return [rec, sales, cogs, assets, curr_assets, ppe, dep, sga, debt, ni, cfo]

        # Try current period (year=0)
        f = get_fields(year=0)
        f2 = get_fields(year=1)
        if not any(pd.isna(v) for v in f):
            rec_y1, sales_y1, cogs_y1, assets_y1, curr_assets_y1, ppe_y1, dep_y1, sga_y1, debt_y1, ni_y1, cfo_y1 = f
            rec_y2, sales_y2, cogs_y2, assets_y2, curr_assets_y2, ppe_y2, dep_y2, sga_y2, debt_y2, ni_y2, cfo_y2 = f2
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
        # If missing, try previous period (year=1)
        f3 = get_fields(year=2)
        if not any(pd.isna(v) for v in f2):
            rec_y1, sales_y1, cogs_y1, assets_y1, curr_assets_y1, ppe_y1, dep_y1, sga_y1, debt_y1, ni_y1, cfo_y1 = f2
            rec_y2, sales_y2, cogs_y2, assets_y2, curr_assets_y2, ppe_y2, dep_y2, sga_y2, debt_y2, ni_y2, cfo_y2 = f3
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
            note = "Used last available complete data (Previous Period)."
            return {"Beneish M-Score": m_score, "note": note}
        return {"error": "Missing critical data for Beneish Score."}

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
