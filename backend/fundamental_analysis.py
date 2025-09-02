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

        def get_fields(year=0, max_years=5):
            def locf(getter, *args):
                for y in range(year, max_years):
                    v = getter(*args, y)
                    if v is not None and not pd.isna(v):
                        return v, y
                return np.nan, None
            ni, ni_y = locf(lambda df, keys, y: _safe_get(df, keys, y) or _safe_fmp_get(fmp_data, 'income_statement', 'netIncome', y), fs, ['Net Income'])
            assets, assets_y = locf(lambda df, keys, y: _safe_get(df, keys, y) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalAssets', y), bs, ['Total Assets'])
            roa = ni / assets if assets and ni is not None else 0
            ocf, ocf_y = locf(lambda df, keys, y: _safe_get(df, keys, y) or _safe_fmp_get(fmp_data, 'cash_flow', 'operatingCashFlow', y), cf, ['Operating Cash Flow', 'Cash Flow from Operations'])
            rev, rev_y = locf(lambda df, keys, y: _safe_get(df, keys, y) or _safe_fmp_get(fmp_data, 'income_statement', 'revenue', y), fs, ['Total Revenue'])
            cogs, cogs_y = locf(lambda df, keys, y: _safe_get(df, keys, y) or _safe_fmp_get(fmp_data, 'income_statement', 'costOfRevenue', y), fs, ['Cost Of Revenue'])
            gp = rev - cogs if rev is not None and cogs is not None else np.nan
            gm = gp / rev if rev and gp is not None else 0
            debt, debt_y = locf(lambda df, keys, y: _safe_get(df, keys, y) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalDebt', y), bs, ['Total Debt', 'Long Term Debt'])
            curr_assets, ca_y = locf(lambda df, keys, y: _safe_get(df, keys, y) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentAssets', y), bs, ['Current Assets'])
            curr_liab, cl_y = locf(lambda df, keys, y: _safe_get(df, keys, y) or _safe_fmp_get(fmp_data, 'balance_sheet', 'totalCurrentLiabilities', y), bs, ['Current Liabilities'])
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
            imputed = [k for k, v in zip(fields.keys(), [ni_y, assets_y, ocf_y, rev_y, cogs_y, debt_y, ca_y, cl_y]) if v not in [0, None]]
            return fields, imputed

        # Try current period (year=0)
        f, imputed = get_fields(year=0)
        f2, imputed2 = get_fields(year=1)
        data_points = [f['roa'], f['ocf'], f['debt'], f['cr'], f['shares'], f['gm'], f['rev'], f['assets']]
        if not any(v is None or pd.isna(v) for v in data_points):
            # ...existing code for delta calculations...
            # ...unchanged...
            f2, _ = get_fields(year=1)
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
            note = None
            if imputed:
                note = f"Some fields imputed using last available historical value: {', '.join(imputed)}."
            return {"Piotroski F-Score": f_score, **({"note": note} if note else {})}
        # If missing, try previous period (year=1)
        data_points_prev = [f2['roa'], f2['ocf'], f2['debt'], f2['cr'], f2['shares'], f2['gm'], f2['rev'], f2['assets']]
        if not any(v is None or pd.isna(v) for v in data_points_prev):
            # ...existing code for delta calculations...
            # ...unchanged...
            f3, _ = get_fields(year=2)
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
            note = None
            if imputed2:
                note = f"Some fields imputed using last available historical value: {', '.join(imputed2)}."
            return {"Piotroski F-Score": f_score, **({"note": note} if note else {})}
        # If still missing, impute all missing fields with last available value and calculate
        # For each field, try to get last available value from up to max_years
        f_impute, imputed_fields = get_fields(year=0, max_years=5)
        f_score = sum([
            1 if f_impute['roa'] > 0 else 0,
            1 if f_impute['ocf'] > 0 else 0,
            1 if f_impute['ocf'] > f_impute['roa'] else 0,
            1 if f_impute['roa'] > 0 else 0,
            1 if (f_impute['debt'] / f_impute['assets'] if f_impute['assets'] else 0) < 1 else 0,
            1 if f_impute['cr'] > 0 else 0,
            1 if f_impute['shares'] is not None else 0,
            1 if f_impute['gm'] > 0 else 0,
            1 if (f_impute['rev'] / f_impute['assets'] > 0 if f_impute['assets'] else 0) else 0
        ])
        note = f"All missing fields imputed using last available historical value: {', '.join(imputed_fields)}. Score may be less reliable."
        return {"Piotroski F-Score": f_score, "note": note}

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


        def locf_with_fmp(df, keys, fmp_type, fmp_key, max_years=5):
            for y in range(0, max_years):
                v = _safe_get(df, keys, y)
                if v is not None and not pd.isna(v):
                    return v, f"year_{y}", v
                v_fmp = _safe_fmp_get(fmp_data, fmp_type, fmp_key, y)
                if v_fmp is not None and not pd.isna(v_fmp):
                    return v_fmp, f"fmp_{y}", v_fmp
            return np.nan, None, np.nan
        def get_fields(year=0, max_years=5):
            wc, wc_src, wc_val = locf_with_fmp(bs, ['Working Capital'], 'balance_sheet', 'workingCapital', max_years)
            if pd.isna(wc):
                ca, ca_src, ca_val = locf_with_fmp(bs, ['Current Assets'], 'balance_sheet', 'totalCurrentAssets', max_years)
                cl, cl_src, cl_val = locf_with_fmp(bs, ['Current Liabilities'], 'balance_sheet', 'totalCurrentLiabilities', max_years)
                wc = ca - cl if ca is not None and cl is not None else np.nan
                wc_src = f"{ca_src} - {cl_src}" if ca_src and cl_src else None
                wc_val = f"{ca_val} - {cl_val}" if ca_val and cl_val else np.nan
            ta, ta_src, ta_val = locf_with_fmp(bs, ['Total Assets'], 'balance_sheet', 'totalAssets', max_years)
            re, re_src, re_val = locf_with_fmp(bs, ['Retained Earnings'], 'balance_sheet', 'retainedEarnings', max_years)
            ebit, ebit_src, ebit_val = locf_with_fmp(fs, ['EBIT', 'Operating Income'], 'income_statement', 'operatingIncome', max_years)
            if pd.isna(ebit):
                ni, ni_src, ni_val = locf_with_fmp(fs, ['Net Income'], 'income_statement', 'netIncome', max_years)
                interest, int_src, int_val = locf_with_fmp(fs, ['Interest Expense'], 'income_statement', 'interestExpense', max_years)
                taxes, tax_src, tax_val = locf_with_fmp(fs, ['Tax Provision'], 'income_statement', 'incomeTaxExpense', max_years)
                if all(pd.notna([ni, interest, taxes])):
                    ebit = ni + interest + taxes
                    ebit_src = f"{ni_src}+{int_src}+{tax_src}"
                    ebit_val = f"{ni_val}+{int_val}+{tax_val}"
            mve = info.get('marketCap')
            tl, tl_src, tl_val = locf_with_fmp(bs, ['Total Liab', 'Total Liabilities'], 'balance_sheet', 'totalLiabilities', max_years)
            sales, sales_src, sales_val = locf_with_fmp(fs, ['Total Revenue', 'Revenue'], 'income_statement', 'revenue', max_years)
            fields = {
                'Working Capital': wc,
                'Total Assets': ta,
                'Retained Earnings': re,
                'EBIT': ebit,
                'Market Value of Equity': mve,
                'Total Liabilities': tl,
                'Sales': sales
            }
            sources = {
                'Working Capital': wc_src,
                'Total Assets': ta_src,
                'Retained Earnings': re_src,
                'EBIT': ebit_src,
                'Market Value of Equity': 'info',
                'Total Liabilities': tl_src,
                'Sales': sales_src
            }
            values = {
                'Working Capital': wc_val,
                'Total Assets': ta_val,
                'Retained Earnings': re_val,
                'EBIT': ebit_val,
                'Market Value of Equity': mve,
                'Total Liabilities': tl_val,
                'Sales': sales_val
            }
            imputed = [k for k, v in sources.items() if v and (v.startswith('fmp') or 'year_' in v)]
            return fields, imputed, sources, values

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
        # If still missing, impute all missing fields with last available value and calculate
        fields_impute, imputed_fields, sources, values = get_fields(year=0, max_years=5)
        missing_impute = [k for k, v in fields_impute.items() if v is None or pd.isna(v)]
        if not missing_impute and fields_impute['Total Assets'] != 0 and fields_impute['Total Liabilities'] != 0:
            A = fields_impute['Working Capital'] / fields_impute['Total Assets']
            B = fields_impute['Retained Earnings'] / fields_impute['Total Assets']
            C = fields_impute['EBIT'] / fields_impute['Total Assets']
            D = fields_impute['Market Value of Equity'] / fields_impute['Total Liabilities']
            E = fields_impute['Sales'] / fields_impute['Total Assets']
            value_details = ', '.join([f"{k}: {values[k]} (source: {sources[k]})" for k in fields_impute])
            note = f"All missing fields imputed using last available value or FMP: {', '.join(imputed_fields)}. Values used: {value_details}. Score may be less reliable."
            return {"Altman Z-Score": z_score, "note": note}
        msg = f"Missing non-calculable data for Z-Score. Missing fields: {', '.join(missing)}. "
        return {"error": msg.strip()}

    except Exception as e:
        logger.error(f"Altman Z-Score calculation failed: {e}")
        return {"error": "An unexpected error occurred during Altman Z-Score calculation."}


def get_beneish_m_score(fs, bs, cf, fmp_data):
    """Calculates the Beneish M-Score for earnings manipulation risk."""
    try:
        if len(fs.columns) < 2 or len(bs.columns) < 2 or len(cf.columns) < 2:
            return {"error": "Not enough historical data for Beneish score."}

        def locf_with_fmp(df, keys, fmp_type, fmp_key, max_years=5):
            for y in range(0, max_years):
                v = _safe_get(df, keys, y)
                if v is not None and not pd.isna(v):
                    return v, f"year_{y}", v
                v_fmp = _safe_fmp_get(fmp_data, fmp_type, fmp_key, y)
                if v_fmp is not None and not pd.isna(v_fmp):
                    return v_fmp, f"fmp_{y}", v_fmp
            return np.nan, None, np.nan
        def get_fields(year=0, max_years=5):
            rec, rec_src, rec_val = locf_with_fmp(bs, ['Accounts Receivable'], 'balance_sheet', 'netReceivables', max_years)
            sales, sales_src, sales_val = locf_with_fmp(fs, ['Total Revenue'], 'income_statement', 'revenue', max_years)
            cogs, cogs_src, cogs_val = locf_with_fmp(fs, ['Cost Of Revenue'], 'income_statement', 'costOfRevenue', max_years)
            assets, assets_src, assets_val = locf_with_fmp(bs, ['Total Assets'], 'balance_sheet', 'totalAssets', max_years)
            curr_assets, ca_src, ca_val = locf_with_fmp(bs, ['Current Assets'], 'balance_sheet', 'totalCurrentAssets', max_years)
            ppe, ppe_src, ppe_val = locf_with_fmp(bs, ['Property Plant And Equipment', 'Net Property, Plant and Equipment'], 'balance_sheet', 'propertyPlantAndEquipmentNet', max_years)
            dep, dep_src, dep_val = locf_with_fmp(cf, ['Depreciation And Amortization', 'Depreciation'], 'cash_flow', 'depreciationAndAmortization', max_years)
            sga, sga_src, sga_val = locf_with_fmp(fs, ['Selling General And Administration'], 'income_statement', 'sellingAndMarketingExpenses', max_years)
            debt, debt_src, debt_val = locf_with_fmp(bs, ['Total Debt'], 'balance_sheet', 'totalDebt', max_years)
            ni, ni_src, ni_val = locf_with_fmp(fs, ['Net Income'], 'income_statement', 'netIncome', max_years)
            cfo, cfo_src, cfo_val = locf_with_fmp(cf, ['Operating Cash Flow'], 'cash_flow', 'operatingCashFlow', max_years)
            fields = [rec, sales, cogs, assets, curr_assets, ppe, dep, sga, debt, ni, cfo]
            sources = [rec_src, sales_src, cogs_src, assets_src, ca_src, ppe_src, dep_src, sga_src, debt_src, ni_src, cfo_src]
            values = [rec_val, sales_val, cogs_val, assets_val, ca_val, ppe_val, dep_val, sga_val, debt_val, ni_val, cfo_val]
            names = ['Accounts Receivable', 'Total Revenue', 'Cost Of Revenue', 'Total Assets', 'Current Assets', 'Property Plant And Equipment', 'Depreciation', 'Selling General And Administration', 'Total Debt', 'Net Income', 'Operating Cash Flow']
            imputed = [name for name, src in zip(names, sources) if src and (src.startswith('fmp') or 'year_' in src)]
            return fields, imputed, sources, values, names

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
        # If still missing, impute all missing fields with last available value and calculate
        f_impute, imputed_fields, sources, values, names = get_fields(year=0, max_years=5)
        if not any(pd.isna(v) for v in f_impute):
            rec_y1, sales_y1, cogs_y1, assets_y1, curr_assets_y1, ppe_y1, dep_y1, sga_y1, debt_y1, ni_y1, cfo_y1 = [float(v) if hasattr(v, '__len__') and not isinstance(v, str) and np.size(v) == 1 else v for v in f_impute]
            # Use same values for y2 for simplicity (since all are imputed)
            rec_y2, sales_y2, cogs_y2, assets_y2, curr_assets_y2, ppe_y2, dep_y2, sga_y2, debt_y2, ni_y2, cfo_y2 = rec_y1, sales_y1, cogs_y1, assets_y1, curr_assets_y1, ppe_y1, dep_y1, sga_y1, debt_y1, ni_y1, cfo_y1
            dsri = (rec_y1 / sales_y1) / (rec_y2 / sales_y2) if all([sales_y1 != 0, sales_y2 != 0]) else 1.0
            gm_y1 = (sales_y1 - cogs_y1) / sales_y1 if sales_y1 != 0 else 0
            gm_y2 = (sales_y2 - cogs_y2) / sales_y2 if sales_y2 != 0 else 0
            gmi = gm_y2 / gm_y1 if gm_y1 != 0 else 1.0
            aqi = (1 - ((curr_assets_y1 + ppe_y1) / assets_y1)) / (1 - ((curr_assets_y2 + ppe_y2) / assets_y2)) if all([assets_y1 != 0, assets_y2 != 0]) else 1.0
            sgi = sales_y1 / sales_y2 if sales_y2 != 0 else 1.0
            depi = (dep_y2 / (ppe_y2 + dep_y2) if (ppe_y2 + dep_y2) != 0 else 0) / (dep_y1 / (ppe_y1 + dep_y1) if (ppe_y1 + dep_y1) != 0 else 1)
            sgai = (sga_y1 / sales_y1) / (sga_y2 / sales_y2) if all([sales_y1 != 0, sales_y2 != 0]) else 1.0
            lvgi = (debt_y1 / assets_y1) / (debt_y2 / assets_y2) if all([assets_y1 != 0, assets_y2 != 0, debt_y2 != 0]) else 1.0
            tata = (ni_y1 - cfo_y1) / assets_y1 if assets_y1 != 0 else 0.0
            m_score = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi +
                       0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)
            value_details = ', '.join([f"{name}: {val} (source: {src})" for name, val, src in zip(names, values, sources)])
            note = f"All missing fields imputed using last available value or FMP: {', '.join(imputed_fields)}. Values used: {value_details}. Score may be less reliable."
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
