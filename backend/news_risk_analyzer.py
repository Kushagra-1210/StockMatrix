# backend/news_risk_analyzer.py

import random

def fetch_news_risk(ticker: str, basis: str = "annual") -> dict:
    print(f"News Risk basis = {basis}")
    """
    Simulate geopolitical and financial risk signals based on company/ticker.
    In production, connect this to real APIs like GDELT, NewsAPI, or RavenPack.
    """
    # Simulated headlines and risk signals (replace with real API in future)
    dummy_headlines = [
        {"title": f"{ticker} faces regulatory scrutiny", "risk": "High"},
        {"title": f"{ticker} announces expansion into Asia", "risk": "Low"},
        {"title": f"{ticker} hit by global supply chain issues", "risk": "Medium"},
        {"title": f"{ticker} stock rallies after earnings", "risk": "Low"},
        {"title": f"{ticker} under investigation for tax evasion", "risk": "High"},
    ]

    # Randomly sample 3 news items
    selected_news = random.sample(dummy_headlines, 3)

    # Risk scoring logic (Low = 0, Medium = 5, High = 10)
    risk_score = sum(10 if n["risk"] == "High" else 5 if n["risk"] == "Medium" else 0 for n in selected_news)
    risk_score_normalized = round(100 - (risk_score / 30) * 100, 2)  # Inverted: Lower risk → Higher score

    return {
        "news": selected_news,
        "risk_score": risk_score_normalized,
        "verdict": "Safe" if risk_score_normalized >= 70 else "Watch" if risk_score_normalized >= 50 else "Risky"
    }
