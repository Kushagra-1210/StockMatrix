# backend/leaderboard_engine.py
from backend.technical_analysis import analyze_technical_indicators
from backend.fundamental_analysis import analyze_fundamentals
from backend.sentiment_analysis import analyze_sentiment
from backend.news_risk_analyzer import fetch_news_risk
from backend.market_selector import get_top_50_tickers
from backend.screener_engine import calculate_volatility
import pandas as pd

def get_leaderboard(exchange, category, basis = "annual"):
    tickers = get_top_50_tickers(exchange)
    results = []

    for ticker in tickers:
        try:
            fa = analyze_fundamentals(ticker, basis = basis)
            ta = analyze_technical_indicators(ticker, basis = basis)
            sent = analyze_sentiment(ticker, basis = basis)
            news = fetch_news_risk(ticker, basis = basis)
            vol = calculate_volatility(ticker)

            if any("error" in r for r in [fa, ta, sent, news]):
                continue

            final_score = 0.35 * fa["fa_score"] + 0.35 * ta["ta_score"] + 0.2 * sent["score"] * 10 + 0.1 * news["risk_score"]
            data = {
                "Ticker": ticker,
                "FA Score": fa["fa_score"],
                "TA Score": ta["ta_score"],
                "Sentiment": sent["score"] * 10,
                "News Risk": news["risk_score"],
                "Volatility": vol,
                "Market Cap": fa["market_cap"],
                "Final Score": round(final_score, 2),
                "Verdict": fa["verdict"],
                "Period": basis.title()  # Add this line
            }
            results.append(data)
        except:
            continue

    df = pd.DataFrame(results)

    if category == "Top 5 Strong Buys":
        return df.sort_values("Final Score", ascending=False).head(5)

    elif category == "Top 5 Undervalued Stocks":
        return df[df["FA Score"] >= 60].sort_values("FA Score", ascending=False).head(5)

    elif category == "Top 5 Bullish Momentum":
        return df[df["TA Score"] >= 60].sort_values("TA Score", ascending=False).head(5)

    elif category == "Top 5 Low Risk":
        return df.sort_values("Volatility").head(5)

    elif category == "Top 5 High Volatility":
        return df.sort_values("Volatility", ascending=False).head(5)

    elif category == "Top 5 Negative Sentiment":
        return df.sort_values("Sentiment").head(5)

    elif category == "Top 5 Midcap Opportunities":
        midcap_df = df[(df["Market Cap"] > 1e9) & (df["Market Cap"] < 10e9)]
        return midcap_df.sort_values("Final Score", ascending=False).head(5)

    return pd.DataFrame()
