# backend/leaderboard_engine.py
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from .technical_analysis import analyze_technical_indicators
from .fundamental_analysis import analyze_fundamentals
from .sentiment_analysis import analyze_perception
from .news_risk_analyzer import fetch_news_risk
from .market_selector import get_top_50_tickers
from backend.data_fetcher import get_ticker_data

logger = logging.getLogger(__name__)

# --- NEW: Worker function for concurrent leaderboard processing ---
def _process_ticker_for_leaderboard(ticker: str) -> dict | None:
    """
    Analyzes a single ticker for the leaderboard. Designed to be run in a separate thread.
    Returns a dictionary of scores if successful, otherwise None.
    """
    try:
        ticker_data = get_ticker_data(ticker)
        if "error" in ticker_data:
            logging.warning(f"Skipping {ticker} for leaderboard: Could not fetch initial data.")
            return None
            
        industry = ticker_data.get("info", {}).get("sector", "default")
        
        # 1. Call all four analysis modules
        fa = analyze_fundamentals(ticker)
        ta = analyze_technical_indicators(ticker, industry=industry, basis="annual")
        perception = analyze_perception(ticker)
        news_risk = fetch_news_risk(ticker)

        # 2. Robustly check if any analysis failed
        if "error" in fa or "error" in ta or "error" in perception or "error" in news_risk:
            logging.warning(f"Skipping {ticker} for leaderboard due to an analysis error.")
            return None

        # 3. Extract and scale scores
        fa_score = fa.get("Fundamental Score", 50)
        ta_score = ta.get("ta_score", 50)
        perception_score = perception.get("strategic_perception_score", 10) * 5
        safety_score = 100 - news_risk.get("risk_score", 50)

        # 4. Calculate final weighted score
        final_score = (0.35 * fa_score) + (0.35 * ta_score) + (0.20 * perception_score) + (0.10 * safety_score)
        
        return {
            "Ticker": ticker,
            "FA Score": round(fa_score, 2),
            "TA Score": round(ta_score, 2),
            "Perception Score": round(perception_score, 2),
            "News Score": round(safety_score, 2),
            "Final Score": round(final_score, 2)
        }
    except Exception as e:
        logging.critical(f"Unexpected critical error in leaderboard worker for {ticker}: {e}", exc_info=True)
        return None

# --- REFACTORED: Main leaderboard function using ThreadPoolExecutor ---
def get_leaderboard(exchange: str) -> pd.DataFrame:
    """
    Generates a stock leaderboard by concurrently analyzing stocks using a thread pool.
    """
    tickers = get_top_50_tickers(exchange)
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ticker = {executor.submit(_process_ticker_for_leaderboard, ticker): ticker for ticker in tickers}
        
        for future in as_completed(future_to_ticker):
            result = future.result()
            if result:
                results.append(result)

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    return df.sort_values("Final Score", ascending=False).reset_index(drop=True)
