# backend/news_risk_analyzer.py

import requests
import logging
from datetime import datetime, timedelta

# Initialize a logger for this module
logger = logging.getLogger(__name__)

# --- Configuration for the News API ---
# Replace with your actual Marketaux API token if you have one.
# For now, it will use a generic news source.
MARKETAUX_API_TOKEN = "MARKETAUX_API_KEY" # IMPORTANT: Replace with your key
NEWS_API_URL = "https://api.marketaux.com/v1/news/all"

# --- Risk Keyword Dictionary ---
# Keywords are categorized by risk type. You can expand this list.
RISK_KEYWORDS = {
    "financial_distress": ["bankrupt", "default", "insolvent", "restructuring", "downgrade", "liquidity crisis"],
    "legal_regulatory": ["lawsuit", "investigation", "probe", "regulation", "fine", "settlement", "doj"],
    "geopolitical": ["trade war", "sanctions", "tariff", "geopolitical tension", "unrest", "embargo"],
    "management_crisis": ["scandal", "resignation", "fraud", "misconduct", "ceo change"],
    "negative_outlook": ["headwinds", "challenging", "weak demand", "guidance cut", "profit warning"]
}

def fetch_news_risk(ticker: str, basis: str = "annual") -> dict:
    """
    Fetches news for a ticker, analyzes headlines for risk keywords,
    and calculates a risk score.

    Args:
        ticker (str): The stock ticker to analyze.
        basis (str): The time period for the analysis ('annual' or 'quarterly').

    Returns:
        dict: A dictionary containing the risk score, verdict, and relevant headlines.
              Returns an error dictionary if fetching or analysis fails.
    """
    # Determine the date range based on the 'basis'
    days = 365 if basis.lower() == "annual" else 90
    from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    # Parameters for the Marketaux API request
    params = {
        "api_token": MARKETAUX_API_TOKEN,
        "symbols": ticker,
        "published_on_or_after": from_date,
        "language": "en",
        "limit": 25 # Fetch up to 25 recent articles
    }

    try:
        # --- API Call ---
        # Note: This will fail if you haven't replaced "YOUR_API_KEY_HERE".
        # A real implementation would require a valid API key.
        if MARKETAUX_API_TOKEN == "YOUR_API_KEY_HERE":
             return {"error": "Marketaux API key is not set in news_risk_analyzer.py."}

        response = requests.get(NEWS_API_URL, params=params, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        news_data = response.json()

        if not news_data.get("data"):
            return {"error": "No news articles returned from the API."}

        # --- Risk Analysis ---
        risk_score = 0
        risk_headlines = []
        articles_analyzed = 0

        for article in news_data["data"]:
            headline = article.get("title", "").lower()
            if not headline:
                continue

            articles_analyzed += 1
            headline_risk_found = False
            for category, keywords in RISK_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in headline:
                        risk_score += 1 # Increment score for each risk keyword match
                        if not headline_risk_found:
                            risk_headlines.append(article.get("title"))
                            headline_risk_found = True # Add headline only once

        # --- Scoring Logic ---
        # Normalize the risk score. A higher raw score means more risk.
        # We want a final score where 100 is high risk and 0 is low risk.
        if articles_analyzed == 0:
             final_risk_score = 0
        else:
             # Normalize based on the number of potential risk hits.
             # This simple model assumes one potential hit per article.
             normalized_score = (risk_score / articles_analyzed) * 100
             final_risk_score = min(normalized_score, 100) # Cap score at 100

        # Determine a qualitative verdict
        if final_risk_score > 60:
            verdict = "High Risk"
        elif final_risk_score > 30:
            verdict = "Moderate Risk"
        else:
            verdict = "Low Risk"

        return {
            "risk_score": round(final_risk_score, 2),
            "verdict": verdict,
            "headlines": risk_headlines[:5], # Return the top 5 most relevant risk headlines
            "articles_analyzed": articles_analyzed
        }

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error fetching news for {ticker}: {e}")
        return {"error": f"Failed to fetch news (HTTP {e.response.status_code}). Check API key or network."}
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching news for {ticker}: {e}")
        return {"error": "A network error occurred while fetching news."}
    except Exception as e:
        logger.critical(f"An unexpected error occurred in news risk analysis for {ticker}: {e}", exc_info=True)
        return {"error": "An unexpected critical error occurred."}