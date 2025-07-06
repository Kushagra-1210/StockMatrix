import requests
import os
import streamlit as st  # ✅ You forgot this import

def fetch_news_risk(ticker: str, basis: str = "annual") -> dict:
    try:
        # ✅ Use Streamlit secrets or fallback to .env or hardcoded (for local dev)
        api_key = st.secrets.get("MARKETAUX_API_KEY") or os.getenv("MARKETAUX_API_KEY")

        if not api_key:
            return {
                "risk_score": 50.0,
                "verdict": "Watch",
                "news": [],
                "error": "❌ Marketaux API key not set. Please configure it."
            }

        # Select time window based on basis
        date_filter = "90d" if basis.lower() == "quarterly" else "365d"

        params = {
            "api_token": api_key,
            "symbols": ticker,
            "filter_entities": True,
            "language": "en",
            "published_after": date_filter,
            "limit": 5
        }

        response = requests.get("https://api.marketaux.com/v1/news/all", params=params)
        data = response.json()

        if "error" in data or response.status_code != 200:
            return {
                "risk_score": 50.0,
                "verdict": "Watch",
                "news": [],
                "error": "❌ Daily plan for Marketaux API is exhausted. Try again tomorrow."
            }

        articles = data.get("data", [])[:3]

        # Risk scoring based on keywords
        high_risk_words = ["lawsuit", "fraud", "probe", "investigation", "ban", "scam"]
        score = 0
        for article in articles:
            title = article.get("title", "").lower()
            score += any(w in title for w in high_risk_words) * 10

        risk_score = round(100 - min(score, 30) / 30 * 100, 2)
        verdict = "Safe" if risk_score >= 70 else "Watch" if risk_score >= 50 else "Risky"

        return {
            "risk_score": risk_score,
            "verdict": verdict,
            "news": [{"title": a["title"], "url": a.get("url", "#")} for a in articles]
        }

    except Exception as e:
        return {
            "risk_score": 50.0,
            "verdict": "Watch",
            "news": [],
            "error": f"⚠️ News fetch error: {str(e)}"
        }
