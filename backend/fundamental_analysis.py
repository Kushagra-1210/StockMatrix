# backend/fundamental_analysis.py

import yfinance as yf
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# --- Constants for Financial Models ---
# Using Fama-French factors for a more robust cost of equity calculation.
# In a live system, these would be fetched daily from a source like the Kenneth R. French Data Library.
# Using recent approximate annual factors as placeholders.
FAMA_FRENCH_FACTORS = {
    "Mkt-RF": 0.06,  # Market Risk Premium
    "SMB": 0.02,     # Size Premium (Small Minus Big)
    "HML": 0.04      # Value Premium (High Minus Low)
}
FALLBACK_GROWTH_RATE = 0.03
FALLBACK_WACC = 0.09

# Cached function to avoid fetching the risk-free rate repeatedly
def get_risk_free_rate():
    """Fetches the 10-Year US Treasury Yield as a proxy for the risk-free rate."""
    try:
        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="1mo")
        if not hist.empty:
            return hist['Close'].iloc[-1] / 100
    except Exception as e:
        logging.warning(f"Could not fetch risk-free rate. Error: {e}")
    return 0.04 # Fallback value if API fails

def _get_analyst_growth_estimate(stock_info: dict) -> tuple[float | None, str]:
    """
    Prioritizes analyst 5-year growth estimates from yfinance info.
    Returns the growth rate and a confidence string.
    """
    if 'earningsGrowth' in stock_info and stock_info['earningsGrowth']:
        return stock_info['earningsGrowth'], "Analyst Estimate"
    if 'revenueGrowth' in stock_info and stock_info['revenueGrowth']:
        return stock_info['revenueGrowth'], "Analyst Revenue Estimate"
    return None, "N/A"

def _calculate_historical_growth_rate(cash_flow_data: pd.DataFrame) -> tuple[float, str]:
    """Calculates historical FCF CAGR as a fallback."""
    try:
        fcf = cash_flow_data.loc['Total Cash From Operating Activities'] + cash_flow_data.loc['Capital Expenditures']
        positive_fcf = fcf[fcf > 0]
        if len(positive_fcf) < 2:
            return FALLBACK_GROWTH_RATE, "Fallback (Insufficient History)"

        start_value = positive_fcf.iloc[-1]
        end_value = positive_fcf.iloc[0]
        num_years = len(positive_fcf) - 1
        cagr = (end_value / start_value) ** (1 / num_years) - 1 if num_years > 0 else 0
        
        # Cap and floor for realism
        return max(-0.05, min(cagr, 0.20)), "Historical CAGR"
    except (KeyError, IndexError):
        return FALLBACK_GROWTH_RATE, "Fallback (Data Error)"

def _calculate_cost_of_equity(stock_info: dict) -> tuple[float | None, str]:
    """
    Calculates Cost of Equity using the Fama-French 3-Factor Model.
    Re = Rf + Beta * (Mkt-RF) + s * (SMB) + h * (HML)
    """
    confidence_report = []
    
    risk_free_rate = get_risk_free_rate()
    beta = stock_info.get("beta")
    
    if beta is None:
        confidence_report.append("Beta: Fallback (Not Available)")
        beta = 1.0 # Assume market risk if Beta is missing
    else:
        confidence_report.append("Beta: Dynamic")

    # For simplicity, size (s) and value (h) factor loadings are assumed to be 1.
    # A more rigorous model would calculate these via regression analysis.
    ff = FAMA_FRENCH_FACTORS
    cost_of_equity = risk_free_rate + (beta * ff["Mkt-RF"]) + (1 * ff["SMB"]) + (1 * ff["HML"])
    
    return cost_of_equity, ", ".join(confidence_report)

def _calculate_wacc(stock_info: dict, balance_sheet_data: pd.DataFrame, financials_data: pd.DataFrame) -> tuple[float, str]:
    """Calculates WACC, now using the Fama-French cost of equity."""
    cost_of_equity, coe_confidence = _calculate_cost_of_equity(stock_info)
    if cost_of_equity is None:
        return FALLBACK_WACC, f"CoE: Fallback, {coe_confidence}"

    try:
        total_debt = balance_sheet_data.loc['Total Debt'].iloc[0]
        interest_expense = abs(financials_data.loc['Interest Expense'].iloc[0])
        cost_of_debt = interest_expense / total_debt if total_debt > 0 else 0

        income_before_tax = financials_data.loc['Income Before Tax'].iloc[0]
        income_tax_expense = financials_data.loc['Income Tax Expense'].iloc[0]
        tax_rate = income_tax_expense / income_before_tax if income_before_tax > 0 else 0.21

        market_cap = stock_info.get("marketCap")
        firm_value = market_cap + total_debt
        
        weight_of_equity = market_cap / firm_value
        weight_of_debt = total_debt / firm_value

        wacc = (weight_of_equity * cost_of_equity) + (weight_of_debt * cost_of_debt * (1 - tax_rate))
        
        return wacc if wacc > 0 else FALLBACK_WACC, f"CoE: {coe_confidence}, WACC: Dynamic"

    except (KeyError, IndexError, TypeError, ZeroDivisionError):
        return FALLBACK_WACC, f"CoE: {coe_confidence}, WACC: Fallback (Data Error)"

def _calculate_dcf_valuation(cash_flow_data: pd.DataFrame, wacc: float, fcf_growth_rate: float, shares_outstanding: int, total_debt: float, cash_and_equivalents: float) -> dict:
    """Performs the core DCF calculation."""
    try:
        last_year_fcf = cash_flow_data.loc['Total Cash From Operating Activities'].iloc[0] + cash_flow_data.loc['Capital Expenditures'].iloc[0]

        future_fcf = [last_year_fcf * ((1 + fcf_growth_rate) ** year) for year in range(1, 6)]
        
        terminal_growth_rate = 0.02
        terminal_value = (future_fcf[-1] * (1 + terminal_growth_rate)) / (wacc - terminal_growth_rate)

        discounted_fcf = [fcf / ((1 + wacc) ** (i + 1)) for i, fcf in enumerate(future_fcf)]
        discounted_terminal_value = terminal_value / ((1 + wacc) ** 5)

        enterprise_value = sum(discounted_fcf) + discounted_terminal_value
        equity_value = enterprise_value - total_debt + cash_and_equivalents
        
        return {"dcf_intrinsic_value": equity_value / shares_outstanding}

    except (KeyError, IndexError, TypeError, ZeroDivisionError) as e:
        return {"error": f"DCF calculation failed: {e}"}


def analyze_fundamentals(ticker: str, basis: str = "annual") -> dict:
    """Analyzes fundamentals using a dynamic, multi-factor DCF model."""
    if basis.lower() != "annual":
        return {"error": "DCF analysis requires annual data."}

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        cf, bs, fin = stock.cashflow, stock.balance_sheet, stock.financials

        if any(df.empty for df in [cf, bs, fin]):
            return {"error": "Annual financial data is not available."}

        # --- DYNAMIC RATE AND CONFIDENCE REPORTING ---
        confidence_report = {}
        fcf_growth_rate, growth_source = _get_analyst_growth_estimate(info)
        if fcf_growth_rate is None:
            fcf_growth_rate, growth_source = _calculate_historical_growth_rate(cf)
        confidence_report["Growth Rate Source"] = growth_source
        
        wacc, wacc_source = _calculate_wacc(info, bs, fin)
        confidence_report["WACC Source"] = wacc_source

        # --- Perform DCF Valuation ---
        dcf_result = _calculate_dcf_valuation(
            cf, wacc, fcf_growth_rate,
            info.get("sharesOutstanding"),
            bs.loc['Total Debt'].iloc[0],
            bs.loc['Cash And Cash Equivalents'].iloc[0]
        )
        if "error" in dcf_result:
            return dcf_result

        intrinsic_value = dcf_result["dcf_intrinsic_value"]
        current_price = info.get("currentPrice")

        if not current_price:
            return {"error": "Current stock price not available."}

        upside_potential = ((intrinsic_value - current_price) / current_price) * 100
        verdict = "Undervalued" if upside_potential > 20 else "Fairly Valued" if -10 <= upside_potential <= 20 else "Overvalued"
        
        capped_upside = max(-100, min(100, upside_potential))
        dcf_score = (capped_upside + 100) / 2

        return {
            "current_price": round(current_price, 2),
            "dcf_intrinsic_value": round(intrinsic_value, 2),
            "upside_potential": round(upside_potential, 2),
            "verdict": verdict,
            "dcf_score": round(dcf_score, 2),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector", "N/A"),
            "confidence_report": confidence_report, # The new confidence report
            "period": "Annual"
        }

    except Exception as e:
        logging.error(f"Fundamental analysis failed for {ticker}: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred during fundamental analysis."}