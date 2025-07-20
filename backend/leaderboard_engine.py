# backend/leaderboard_engine.py
import pandas as pd
import logging
from backend.technical_analysis import analyze_technical_indicators
from backend.fundamental_analysis import analyze_fundamentals
from backend.sentiment_analysis import analyze_sentiment
from backend.news_risk_analyzer import fetch_news_risk
from backend.market_selector import get_top_50_tickers
from backend.screener_engine import calculate_volatility

def get_leaderboard(exchange, category):
    tickers = get_top_50_tickers(exchange)
    results = []

    for ticker in tickers:
        try:
            # --- Analysis (basis is now fixed to annual for DCF) ---
            fa = analyze_fundamentals(ticker, basis="annual")
            ta = analyze_technical_indicators(ticker, basis="annual")
            sent = analyze_sentiment(ticker, basis="annual")
            news = fetch_news_risk(ticker, basis="annual")
            vol = calculate_volatility(ticker)

            if any(isinstance(r, dict) and "error" in r for r in [fa, ta, sent, news]):
                logging.warning(f"Skipping {ticker} for leaderboard due to analysis error.")
                continue

            # --- UPDATED SCORING LOGIC ---
            final_score = (
                0.35 * fa["dcf_score"] +  # Using the new DCF-derived score
                0.35 * ta["ta_score"] +
                0.2 * sent["score"] * 10 +
                0.1 * news["risk_score"]
            )
            data = {
                "Ticker": ticker,
                "Upside (%)": fa["upside_potential"],
                "DCF Score": fa["dcf_score"], # Changed from FA Score
                "TA Score": ta["ta_score"],
                "Sentiment": sent["score"] * 10,
                "News Risk": news["risk_score"],
                "Volatility": vol,
                "Market Cap": fa.get("market_cap"),
                "Final Score": round(final_score, 2)
            }
            results.append(data)

        except KeyError as e:
            logging.error(f"Leaderboard data structure error for {ticker}: Missing key {e}. Skipping.")
            continue
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
        # Now filters based on the DCF score, which represents undervaluation strength
        return df[df["DCF Score"] >= 70].sort_values("DCF Score", ascending=False).head(5)
    # ... (other categories remain the same)
    elif category == "Top 5 Bullish Momentum":
        return df[df["TA Score"] >= 60].sort_values("TA Score", ascending=False).head(5)
    elif category == "Top 5 Low Risk":
        return df.sort_values("Volatility").head(5)
    elif category == "Top 5 High Volatility":
        return df.sort_values("Volatility", ascending=False).head(5)
    elif category == "Top 5 Negative Sentiment":
        return df.sort_values("Sentiment").head(5)
    
    return pd.DataFrame()