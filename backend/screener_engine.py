# backend/screener_engine.py
import pandas as pd
import numpy as np
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from .fundamental_analysis import analyze_fundamentals
from .technical_analysis import analyze_technical_indicators
from .news_risk_analyzer import fetch_news_risk
from backend.data_fetcher import get_ticker_data

# --- Helper function to parse percentage strings ---
def _parse_percentage(pct_string):
    """Converts a percentage string like '25.50%' to a float 25.50."""
    if isinstance(pct_string, str):
        try:
            return float(pct_string.strip().replace('%', ''))
        except (ValueError, TypeError):
            return -999 # Return a value that will fail checks
    return pct_string if isinstance(pct_string, (int, float)) else -999

# --- NEW: Worker function for concurrent processing ---
def _process_ticker_for_screener(ticker: str, min_upside: float, min_ta: float, max_volatility: float) -> dict | None:
    """
    Processes a single ticker for the screener. This function is designed to be run in a separate thread.
    Returns a dictionary with the stock data if it passes the screen, otherwise None.
    """
    try:
        ticker_data = get_ticker_data(ticker)
        if "error" in ticker_data:
            logging.warning(f"Skipping {ticker} in screener: Could not fetch initial data.")
            return None
            
        industry = ticker_data.get("info", {}).get("sector", "default")

        # Run analyses
        fa = analyze_fundamentals(ticker, basis="annual")
        ta = analyze_technical_indicators(ticker, industry=industry, basis="annual")
        vol = calculate_volatility(ticker)

        if any(isinstance(r, dict) and "error" in r for r in [fa, ta]) or vol is None:
            logging.warning(f"Skipping {ticker} in screener due to an analysis error.")
            return None

        # --- Filtering Logic ---
        upside_value = _parse_percentage(fa.get("Upside"))

        if upside_value >= min_upside and ta.get("ta_score", 0) >= min_ta and vol <= max_volatility:
            return {
                "Ticker": ticker,
                "Upside (%)": fa.get("Upside", "N/A"),
                "TA Score": ta.get("ta_score", "N/A"),
                "Volatility (%)": vol,
                "Piotroski Score": fa.get("Piotroski F-Score", "N/A"),
                "Beneish Score": fa.get("Beneish M-Score", "N/A")
            }
        return None # Return None if it doesn't meet criteria
    except Exception as e:
        logging.critical(f"An unexpected error in screener worker for {ticker}: {e}", exc_info=True)
        return None

# --- REFACTORED: Main screener function using ThreadPoolExecutor ---
def screen_stocks(tickers: list, min_upside: float = 0, min_ta: float = 0, max_volatility: float = 100) -> list:
    """
    Screens stocks concurrently using a thread pool for significantly faster execution.
    """
    results = []
    # Using max_workers=10 to balance performance and avoid overwhelming the API provider.
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all ticker processing tasks to the executor
        future_to_ticker = {
            executor.submit(_process_ticker_for_screener, ticker, min_upside, min_ta, max_volatility): ticker 
            for ticker in tickers
        }
        
        for future in as_completed(future_to_ticker):
            result = future.result()
            if result:  # The worker function returns a dict if the stock passes, otherwise None
                results.append(result)

    # Sort the final results by upside percentage
    return sorted(results, key=lambda x: _parse_percentage(x["Upside (%)"]), reverse=True)

def calculate_volatility(ticker: str) -> float | None:
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
