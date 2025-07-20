# backend/leaderboard_engine.py
import pandas as pd
import logging
from .technical_analysis import analyze_technical_indicators
from .fundamental_analysis import analyze_fundamentals
from .sentiment_analysis import analyze_sentiment
from .news_risk_analyzer import fetch_news_risk
from .market_selector import get_top_50_tickers
from .screener_engine import calculate_volatility

# In backend/leaderboard_engine.py

# Add the same helper function here
def _parse_percentage(pct_string):
    """Converts a percentage string like '25.50%' to a float 25.50."""
    if isinstance(pct_string, str):
        return float(pct_string.strip().replace('%', ''))
    return pct_string

def _parse_piotroski(piotroski_string):
    """Converts a Piotroski string like '7/9' to a number 7."""
    if isinstance(piotroski_string, str):
        return int(piotroski_string.split('/')[0])
    return 0

def get_leaderboard(exchange, category):
    tickers = get_top_50_tickers(exchange)
    results = []

    for ticker in tickers:
        try:
            fa = analyze_fundamentals(ticker, basis="annual")
            ta = analyze_technical_indicators(ticker, basis="annual")
            sent = analyze_sentiment(ticker, basis="annual")
            news = fetch_news_risk(ticker, basis="annual")
            vol = calculate_volatility(ticker)

            if any(isinstance(r, dict) and "error" in r for r in [fa, ta, sent, news]):
                logging.warning(f"Skipping {ticker} for leaderboard due to analysis error.")
                continue

            # --- NEW, MORE ROBUST SCORING LOGIC ---
            # Convert raw values to normalized scores (0-100)
            upside_pct = _parse_percentage(fa.get("Upside", "0%"))
            # Cap upside at 200% for scoring to avoid extreme outliers
            upside_score = min(upside_pct, 200) / 2

            piotroski_raw = _parse_piotroski(fa.get("Piotroski F-Score", "0/9"))
            piotroski_score = (piotroski_raw / 9) * 100 # Convert 9-point scale to 100-point scale

            # Combine fundamental scores (60% DCF Upside, 40% Piotroski Health)
            fundamental_score = 0.6 * upside_score + 0.4 * piotroski_score

            final_score = (
                0.40 * fundamental_score +
                0.30 * ta.get("ta_score", 0) +
                0.20 * sent.get("score", 0) * 10 +
                0.10 * (100 - news.get("risk_score", 50)) # Invert risk score
            )
            data = {
                "Ticker": ticker,
                "Upside (%)": fa.get("Upside", "N/A"),
                "TA Score": ta.get("ta_score", 0),
                "Piotroski Score": fa.get("Piotroski F-Score", "N/A"),
                "Final Score": round(final_score, 2)
            }
            results.append(data)

        except Exception as e:
            logging.critical(f"Unexpected error for {ticker} in leaderboard: {e}", exc_info=True)
            continue

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    # --- UPDATED CATEGORY FILTERING ---
    if category == "Top 5 Strong Buys":
        return df.sort_values("Final Score", ascending=False).head(5)
    elif category == "Top 5 Undervalued Stocks":
        df['upside_numeric'] = df['Upside (%)'].apply(_parse_percentage)
        return df.sort_values("upside_numeric", ascending=False).head(5)
    elif category == "Top 5 Financially Strong":
        df['piotroski_numeric'] = df['Piotroski Score'].apply(_parse_piotroski)
        return df.sort_values("piotroski_numeric", ascending=False).head(5)
    # ... other categories can be updated similarly ...
    
    return df.sort_values("Final Score", ascending=False)
