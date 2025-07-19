# =============================================================================
# START OF REPLACEMENT CODE: backend/news_risk_analyzer.py
# =============================================================================

import os
import requests
from dotenv import load_dotenv

# --- Secure API Key Loading ---
# This line looks for a .env file in your project's root directory
# and loads the variables from it into the environment.
load_dotenv()

# os.getenv() securely retrieves the key from the environment.
# It will return None if the key is not found.
MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY")

def fetch_news_risk(ticker: str, basis: str = "annual") -> dict:
    """
    Fetches news from Marketaux API and calculates a risk score.
    Returns a dictionary with news, risk_score, and verdict.
    """
    # --- Check for API Key ---
    # This is the primary safeguard. If the key wasn't loaded, the function
    # returns an informative error instead of failing.
    if not MARKETAUX_API_KEY:
        return {
            "risk_score": 50.0,
            "verdict": "Unknown",
            "news": [],
            "error": "Marketaux API Key not found. Please check environment configuration."
        }

    try:
        # Select time window based on basis
        date_filter = "90d" if basis.lower() == "quarterly" else "365d"

        params = {
            "api_token": MARKETAUX_API_KEY,
            "symbols": ticker,
            "filter_entities": True,
            "language": "en",
            "published_after": date_filter,
            "limit": 5
        }

        response = requests.get("https://api.marketaux.com/v1/news/all", params=params, timeout=10)
        response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        if "error" in data:
            error_message = data["error"].get("message", "An unknown API error occurred.")
            return {
                "risk_score": 50.0,
                "verdict": "Unknown",
                "news": [],
                "error": f"API Error: {error_message}"
            }

        articles = data.get("data", [])[:3]

        # Risk scoring based on keywords
        high_risk_words = ["lawsuit", "fraud", "probe", "investigation", "ban", "scam", "breach", "fine", "recall"]
        score = 0
        for article in articles:
            title = article.get("title", "").lower()
            if any(word in title for word in high_risk_words):
                score += 10

        # Normalize the score (0-100, where 100 is safest)
        # Each risky headline reduces the score. Max reduction for 3 headlines is 30.
        risk_score = round(100 - (min(score, 30) / 30 * 100), 2)
        verdict = "Safe" if risk_score >= 70 else "Watch" if risk_score >= 40 else "Risky"

        return {
                "news": [{"title": a.get("title", ""), "url": a.get("url", "")} for a in articles],
                "risk_score": risk_score,
                "verdict": verdict
            }

    except requests.exceptions.Timeout:
        return {
            "risk_score": 50.0, "verdict": "Unknown", "news": [],
            "error": "News fetch failed: The request timed out."
        }
    except requests.exceptions.RequestException as e:
        return {
            "risk_score": 50.0, "verdict": "Unknown", "news": [],
            "error": f"News fetch failed: {str(e)}"
        }
    except Exception as e:
        return {
            "risk_score": 50.0, "verdict": "Unknown", "news": [],
            "error": f"An unexpected error occurred: {str(e)}"
        }

# =============================================================================
# END OF REPLACEMENT CODE
# =============================================================================