# backend/screener_engine.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from .fundamental_analysis import analyze_fundamentals
from .technical_analysis import analyze_technical_indicators

# In backend/screener_engine.py

# Add this helper function at the top of the file
def _parse_percentage(pct_string):
    """Converts a percentage string like '25.50%' to a float 25.50."""
    if isinstance(pct_string, str):
        return float(pct_string.strip().replace('%', ''))
    return pct_string # Return as is if it's already a number

def screen_stocks(tickers: list, min_upside: float = 0, min_ta: float = 0, max_volatility: float = 100) -> list:
    results = []

    for ticker in tickers:
        try:
            ticker_data = get_ticker_data(ticker)
            if "error" in ticker_data:
                logging.warning(f"Skipping {ticker} in screener: Could not fetch data.")
                continue
            # Get the industry from the 'sector' field, defaulting to 'default'
            industry = ticker_data.get("info", {}).get("sector", "default")

            # Using the new, more powerful fundamental analysis function
            fa = analyze_fundamentals(ticker, basis="annual")
            ta = analyze_technical_indicators(ticker, industry=industry, basis="annual")
            vol = calculate_volatility(ticker)

            if any(isinstance(r, dict) and "error" in r for r in [fa, ta]) or vol is None:
                logging.warning(f"Skipping {ticker} in screener due to analysis error.")
                continue

            # --- CORRECTED FILTERING LOGIC ---
            # Use the helper function to convert the 'Upside' string to a number
            upside_value = None
            if fa.get("Upside"): # Check if the key exists before parsing
                upside_value = _parse_percentage(fa.get("Upside"))

            if upside_value is not None and upside_value >= min_upside and ta["ta_score"] >= min_ta and vol <= max_volatility:
                results.append({
                    "Ticker": ticker,
                    "Upside (%)": fa.get("Upside", "N/A"),
                    "TA Score": ta.get("ta_score", "N/A"),
                    "Volatility (%)": vol,
                    "Piotroski Score": fa.get("Piotroski F-Score", "N/A"),
                    "Beneish Score": fa.get("Beneish M-Score", "N/A")
                })

        except Exception as e:
            logging.critical(f"An unexpected error in screener for {ticker}: {e}", exc_info=True)
            continue

    return sorted(results, key=lambda x: _parse_percentage(x["Upside (%)"]), reverse=True)

from backend.data_fetcher import get_ticker_data

def calculate_volatility(ticker: str) -> float:
    """Calculates volatility using centralized data fetcher."""
    try:
        ticker_data = get_ticker_data(ticker)
        hist_dict = ticker_data.get("history", {})
        if not hist_dict or "Close" not in hist_dict:
            return None
        data = pd.DataFrame(hist_dict)
        if data.empty or "Close" not in data:
            return None
        returns = data["Close"].pct_change().dropna()
        if returns.empty:
            return None
        return round(np.std(returns) * 100, 2)
    except Exception as e:
        logging.warning(f"Could not calculate volatility for {ticker}: {e}")
        return None

# Note: This code assumes that the analyze_fundamentals and analyze_technical_indicators functions
# are defined in the backend/fundamental_analysis.py and backend/technical_analysis.py files respectively