# backend/news_risk_analyzer.py
import requests
import logging
import numpy as np
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

# --- 1. Expanded NLP Keyword & Modifier Dictionaries ---
RISK_KEYWORDS = {
    # Financial Risk (High Impact)
    "restatement": 25, "accounting irregularity": 25, "whistleblower": 20, "delisting": 30,
    "bankruptcy": 30, "insolvency": 25, "default": 20, "downgrade": 15,
    # Legal & Regulatory Risk (High Impact)
    "lawsuit": 15, "sec probe": 20, "doj investigation": 20, "class action": 15,
    "ftc fine": 15, "eu antitrust": 15, "regulatory risk": 15, "sanctions": 20,
    # Operational Risk (Medium Impact)
    "shutdown": 10, "plant fire": 15, "cyberattack": 20, "data breach": 20,
    "supply chain disruption": 10, "outage": 10,
    # Leadership & Reputation Risk (Medium Impact)
    "ceo resigns": 15, "management scandal": 15, "executive misconduct": 15,
    "boycott": 10, "protest": 5, "controversy": 10, "backlash": 10,
    # Market Risk (Variable Impact)
    "trade war": 10, "embargo": 15, "volatile": 5, "plunges": 10
}

POSITIVE_MODIFIERS = {
    "dismissed": -1.5, "resolved": -1.2, "cleared": -1.2, "acquitted": -1.5,
    "denies": -0.8, "refutes": -0.8, "upgraded": -1.5, "beats expectations": -1.2,
    "settled": -0.5 # Settling can still imply some fault
}

NEGATIVE_MODIFIERS = {
    "major": 1.5, "severe": 1.8, "unexpected": 1.5, "critical": 2.0,
    "plunges": 1.5, "fails to": 1.3, "misses": 1.3, "investigation into": 1.5
}

REPUTABLE_SOURCES = ["reuters", "bloomberg", "wall street journal", "associated press", "financial times"]

# --- Helper Functions ---
def _fetch_google_news(ticker: str):
    """Fetches news headlines from Google News RSS feed."""
    try:
        url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'xml')
        
        articles = []
        for item in soup.findAll('item')[:30]:
            pub_date_str = item.pubDate.text
            try:
                pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %Z')
                articles.append({
                    "headline": item.title.text.lower(),
                    "source": item.source.text.lower(),
                    "date": pub_date.replace(tzinfo=None)
                })
            except ValueError:
                logger.warning(f"Could not parse date: {pub_date_str}")
                continue
        return articles
    except Exception as e:
        logger.error(f"Failed to fetch Google News for {ticker}: {e}")
        return []

def _calculate_decay(article_date):
    """Calculates a time decay factor. News from today has 1.0 weight, 30 days ago has 0.2."""
    days_old = (datetime.now() - article_date).days
    return max(1.0 - (days_old / 30.0), 0.2)

# --- Main Analysis Function ---
def fetch_news_risk(ticker: str, basis: str = "annual"):
    """
    Analyzes news risk using a context-aware NLP and weighted scoring model.
    """
    articles = _fetch_google_news(ticker)
    if not articles:
        return {"error": "Could not fetch any news articles for the ticker."}

    sentiment_analyzer = SentimentIntensityAnalyzer()
    headline_scores = []
    risk_headlines = []

    for article in articles:
        headline = article['headline']
        base_score = 0
        modifier = 1.0
        
        # 1. Find the most severe risk keyword in the headline
        matched_keywords = []
        for keyword, score in RISK_KEYWORDS.items():
            if re.search(r'\b' + re.escape(keyword) + r'\b', headline):
                base_score = max(base_score, score)
                matched_keywords.append(keyword)
        
        if base_score == 0:
            continue # Skip articles with no relevant risk keywords

        # 2. Check for context-modifying words around the keywords
        for mod, mult in POSITIVE_MODIFIERS.items():
            if mod in headline:
                modifier *= mult # e.g., 1.0 * -1.5 = -1.5 (inverts and amplifies)
        for mod, mult in NEGATIVE_MODIFIERS.items():
            if mod in headline:
                modifier *= mult # e.g., 1.0 * 1.5 = 1.5 (amplifies)

        # 3. Calculate final headline score with all factors
        sentiment_score = sentiment_analyzer.polarity_scores(headline)['compound']
        decay_factor = _calculate_decay(article['date'])
        source_weight = 1.1 if any(source in article['source'] for source in REPUTABLE_SOURCES) else 1.0

        # The final score is a combination of the keyword's base risk, the context modifier,
        # the overall sentiment, the source's reputation, and how recent the news is.
        final_headline_score = (base_score * modifier) * (1 - sentiment_score * 0.25) * source_weight * decay_factor
        
        headline_scores.append(final_headline_score)
        
        if final_headline_score > 5 or final_headline_score < -5: # Only log significant headlines
            risk_headlines.append({
                "headline": article['headline'].title(),
                "score": round(final_headline_score, 2),
                "keywords": matched_keywords
            })

    # 4. Compute Total Company Risk Score
    if not headline_scores:
        total_risk_score = 0 # No risky news found
    else:
        # We use the average of the top 3 most impactful headlines to avoid dilution
        sorted_scores = sorted(headline_scores, key=abs, reverse=True)
        total_risk_score = np.mean(sorted_scores[:3])

    # Normalize score to a 0-100 scale, where 100 is max risk
    # A negative score indicates positive news, so it should map to a very low risk score.
    normalized_score = min(max(total_risk_score * 2.5, 0), 100)

    # 5. Determine Verdict
    if normalized_score >= 75:
        verdict = "🚨 Extreme Risk: Major negative events detected. Maximum caution advised."
    elif normalized_score >= 60:
        verdict = "🔥 High Risk: Significant negative news or red flags present."
    elif normalized_score >= 40:
        verdict = "⚠️ Elevated Risk: Multiple concerning headlines or ongoing issues."
    elif normalized_score >= 20:
        verdict = "🟡 Moderate Risk: Some negative news or moderate risk factors."
    else:
        verdict = "✅ Low Risk: No significant risk detected in recent news."

    return {
        "risk_score": round(normalized_score, 2),
        "verdict": verdict,
        "headlines": sorted(risk_headlines, key=lambda x: abs(x['score']), reverse=True)[:5]
    }
