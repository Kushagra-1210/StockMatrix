import yfinance as yf
import numpy as np
from datetime import datetime

def safe_div(numerator, denominator):
    try:
        if denominator in [0, None, np.nan] or numerator is None:
            return None
        return numerator / denominator
    except:
        return None

def analyze_fundamentals(ticker: str, basis: str = "annual") -> dict:
    if basis.lower() not in ("annual", "quarterly"):
        return {"error": f"Invalid basis '{basis}'. Must be 'annual' or 'quarterly'"}
    
    print(f"FA basis = {basis}")
    stock = yf.Ticker(ticker)
    info = stock.info

    try:
        # Use correct financial statements based on basis
        if basis == "quarterly":
            fin = stock.quarterly_financials
            cf = stock.quarterly_cashflow
            bs = stock.quarterly_balance_sheet
            period_days = 90
        else:
            fin = stock.financials
            cf = stock.cashflow
            bs = stock.balance_sheet
            period_days = 365

        # Get most recent period data
        net_income = fin.loc["Net Income"].iloc[0] if "Net Income" in fin.index else None
        total_equity = bs.loc["Total Stockholder Equity"].iloc[0] if "Total Stockholder Equity" in bs.index else None
        total_debt = bs.loc["Total Debt"].iloc[0] if "Total Debt" in bs.index else None
        revenue = fin.loc["Total Revenue"].iloc[0] if "Total Revenue" in fin.index else None
        prev_revenue = fin.loc["Total Revenue"].iloc[1] if len(fin.loc["Total Revenue"]) > 1 else None
        shares = info.get("sharesOutstanding")
        current_price = info.get("currentPrice")

        # Calculate period-specific metrics
        eps = safe_div(net_income, shares)
        pe_ratio = safe_div(current_price, eps)
        roe = safe_div(net_income, total_equity)
        if roe is not None: roe *= 100
        free_cash_flow = cf.loc["Total Cash From Operating Activities"].iloc[0] - cf.loc["Capital Expenditures"].iloc[0] if "Total Cash From Operating Activities" in cf.index and "Capital Expenditures" in cf.index else None
        revenue_growth = safe_div((revenue - prev_revenue), prev_revenue) if revenue and prev_revenue else None
        debt_to_equity = safe_div(total_debt, total_equity)

        # Get static metrics
        pb_ratio = info.get("priceToBook")
        market_cap = info.get("marketCap")
        sector = info.get("sector", "N/A")
        long_business_summary = info.get("longBusinessSummary", "")
        governance_score = info.get("governanceEpochDate", None)
        esg_score = info.get("esgScores", {}).get("totalEsg", None)
        fiscal_date = info.get("lastFiscalYearEnd", "N/A")

        # Scoring (same weights but now uses period-specific metrics)
        score = 0
        total_weight = 0

        # Revenue Growth (15%)
        if isinstance(revenue_growth, (int, float)):
            total_weight += 15
            score += 15 if revenue_growth > 0.15 else 7.5 if revenue_growth > 0.05 else 0

        # Profitability (15%)
        prof_score = 0
        prof_subs = 0
        if isinstance(eps, (int, float)):
            prof_subs += 1
            prof_score += 5 if eps > 0 else 0
        if isinstance(net_income, (int, float)):
            prof_subs += 1
            prof_score += 5 if net_income > 0 else 0
        if isinstance(roe, (int, float)):
            prof_subs += 1
            prof_score += 5 if roe > 15 else 2.5 if roe > 5 else 0
        if prof_subs > 0:
            total_weight += 15
            score += (prof_score / (prof_subs * 5)) * 15

        # Debt/Equity Ratio (10%)
        if isinstance(debt_to_equity, (int, float)):
            total_weight += 10
            score += 10 if debt_to_equity < 1 else 5 if debt_to_equity < 2 else 0

        # Cash Flow Health (10%)
        if isinstance(free_cash_flow, (int, float)):
            total_weight += 10
            score += 10 if free_cash_flow > 0 else 0

        # Valuation Ratios (10%)
        val_score = 0
        val_subs = 0
        if isinstance(pe_ratio, (int, float)):
            val_subs += 1
            val_score += 5 if 10 <= pe_ratio <= 25 else 2.5 if 5 <= pe_ratio < 10 or 25 < pe_ratio <= 40 else 0
        if isinstance(pb_ratio, (int, float)):
            val_subs += 1
            val_score += 5 if 1 <= pb_ratio <= 5 else 2.5 if pb_ratio < 1 or pb_ratio > 5 else 0
        if val_subs > 0:
            total_weight += 10
            score += (val_score / (val_subs * 5)) * 10

        # Peer Comparison (10%)
        if sector != "N/A":
            total_weight += 10
            score += 5

        # Governance (10%)
        if governance_score is not None:
            total_weight += 10
            score += 10

        # Industry Outlook (10%)
        if sector != "N/A":
            total_weight += 10
            score += 5

        # ESG (5%)
        if isinstance(esg_score, (int, float)):
            total_weight += 5
            score += 5 if esg_score < 30 else 2.5 if esg_score < 50 else 0

        # Company Overview (5%)
        if long_business_summary and len(long_business_summary) > 100:
            total_weight += 5
            score += 5

        # Final FA Score
        fa_score = round((score / total_weight) * 100, 2) if total_weight > 0 else 0
        verdict = "Undervalued" if fa_score >= 70 else "Fair" if fa_score >= 50 else "Overvalued"

        size = "Unknown"
        if isinstance(market_cap, (int, float)):
            if market_cap >= 1e11: size = "Mega Cap"
            elif market_cap >= 2e10: size = "Large Cap"
            elif market_cap >= 2e9: size = "Mid Cap"
            else: size = "Small Cap"

        if isinstance(fiscal_date, (int, float)):
            fiscal_date = datetime.fromtimestamp(fiscal_date).strftime('%Y-%m-%d')

        return {
            "eps": round(eps, 2) if eps is not None else "N/A",
            "roe": round(roe, 2) if isinstance(roe, (int, float)) else "N/A",
            "pe_ratio": round(pe_ratio, 2) if pe_ratio is not None else "N/A",
            "pb_ratio": pb_ratio if pb_ratio is not None else "N/A",
            "de_ratio": round(debt_to_equity, 2) if isinstance(debt_to_equity, (int, float)) else "N/A",
            "fcf": free_cash_flow if free_cash_flow is not None else "N/A",
            "fa_score": fa_score,
            "verdict": verdict,
            "market_cap": market_cap,
            "size": size,
            "sector": sector,
            "fiscal_date": fiscal_date,
            "period": basis.title(),
            "fa_breakdown": {
                "Revenue Growth": "15" if isinstance(revenue_growth, (int, float)) else "N/A",
                "Profitability": round((prof_score / (prof_subs * 5)) * 15, 2) if prof_subs > 0 else "N/A",
                "Debt/Equity Ratio": "10" if isinstance(debt_to_equity, (int, float)) else "N/A",
                "Cash Flow Health": "10" if isinstance(free_cash_flow, (int, float)) else "N/A",
                "Valuation Ratios": round((val_score / (val_subs * 5)) * 10, 2) if val_subs > 0 else "N/A",
                "Peer Comparison": "5" if sector != "N/A" else "N/A",
                "Management & Governance": "10" if governance_score is not None else "N/A",
                "Industry Outlook": "5" if sector != "N/A" else "N/A",
                "ESG Score": "5" if isinstance(esg_score, (int, float)) else "N/A",
                "Company Overview": "5" if long_business_summary and len(long_business_summary) > 100 else "N/A"
            }
        }

    except Exception as e:
        return {"error": f"Fundamental analysis failed: {str(e)}"}