# backend/leaderboard_engine.py
import pandas as pd
import time
import logging
from .technical_analysis import analyze_technical_indicators
from .fundamental_analysis import analyze_fundamentals
from .sentiment_analysis import analyze_perception
from .news_risk_analyzer import fetch_news_risk
from .market_selector import get_top_50_tickers

from backend.data_fetcher import get_ticker_data
logger = logging.getLogger(__name__)

def get_leaderboard(exchange: str):
    """
    Generates a stock leaderboard by combining scores from all four analysis modules.
    """
    tickers = get_top_50_tickers(exchange)
    results = []
    
    for ticker in tickers:
        time.sleep(0.2) # Add a 200ms delay to avoid rate-limiting
        try:
            ticker_data = get_ticker_data(ticker)
            if "error" in ticker_data:
                logging.warning(f"Skipping {ticker} for leaderboard: Could not fetch data.")
                continue
            industry = ticker_data.get("info", {}).get("sector", "default")
            
            # 1. Call all four advanced analysis modules
            fa = analyze_fundamentals(ticker)
            ta = analyze_technical_indicators(ticker, industry=industry, basis="annual")
            perception = analyze_perception(ticker)
            news_risk = fetch_news_risk(ticker)

            # 2. Robustly check if any analysis failed
            if "error" in fa or "error" in ta or "error" in perception or "error" in news_risk:
                logging.warning(f"Skipping {ticker} for leaderboard due to an error.")
                continue

            # 3. Extract and scale scores from each module
            fa_score = fa.get("Fundamental Score", 50)
            ta_score = ta.get("ta_score", 50)
            
            # Scale perception score (0-20) to 0-100
            perception_score_raw = perception.get("strategic_perception_score", 10)
            perception_score = perception_score_raw * 5
            
            # Invert news risk score (0-100) to a "safety score"
            risk_score = news_risk.get("risk_score", 50)
            safety_score = 100 - risk_score

            # 4. Calculate the final 4-factor weighted score
            # Weighting: 35% FA, 35% TA, 20% Perception, 10% News Safety
            final_score = (
                (0.35 * fa_score) +
                (0.35 * ta_score) +
                (0.20 * perception_score) +
                (0.10 * safety_score)
            )
            
            data = {
                "Ticker": ticker,
                "FA Score": round(fa_score, 2),
                "TA Score": round(ta_score, 2),
                "Perception Score": round(perception_score, 2),
                "News Score": round(100 - risk_score, 2),
                "Final Score": round(final_score, 2)
            }
            results.append(data)

        except Exception as e:
            logging.critical(f"Unexpected critical error for {ticker} in leaderboard: {e}", exc_info=True)
            continue

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    return df.sort_values("Final Score", ascending=False).reset_index(drop=True)