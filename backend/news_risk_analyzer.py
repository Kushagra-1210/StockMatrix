# backend/news_risk_analyzer.py
import requests
import logging
import numpy as np
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

# --- 1. Expanded NLP Keyword Dictionary ---
RISK_EVENT_KEYWORDS = {
    "Litigation": {"keywords": ["lawsuit", "sec probe", "class action", "litigation"], "flag": "Red"},
    "Financial Fraud": {"keywords": ["restatement", "accounting irregularity", "whistleblower"], "flag": "Red"},
    "Regulation": {"keywords": ["ftc fine", "eu antitrust", "compliance rules", "regulatory risk"], "flag": "Red"},
    "Geopolitical": {"keywords": ["sanctions", "trade war", "embargo"], "flag": "Yellow"},
    "Operational": {"keywords": ["shutdown", "plant fire", "cyberattack", "supply chain disruption"], "flag": "Yellow"},
    "Leadership Risk": {"keywords": ["ceo resigns", "management scandal", "executive misconduct"], "flag": "Yellow"},
    "Reputation Risk": {"keywords": ["boycott", "protest", "controversy", "backlash"], "flag": "Yellow"}
}
REPUTABLE_SOURCES = ["reuters", "bloomberg", "wall street journal", "associated press"]

# --- Helper Functions ---
def _fetch_google_news(ticker: str):
    """Fetches news headlines from Google News RSS feed."""
    try:
        url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'xml')
        
        articles = []
        for item in soup.findAll('item')[:30]: # Analyze up to 30 recent articles
            pub_date = datetime.strptime(item.pubDate.text, '%a, %d %b %Y %H:%M:%S %Z')
            articles.append({
                "headline": item.title.text.lower(),
                "source": item.source.text.lower(),
                "date": pub_date.replace(tzinfo=None) # Make timezone naive
            })
        return articles
    except Exception as e:
        logger.error(f"Failed to fetch Google News for {ticker}: {e}")
        return []

def _calculate_decay(article_date):
    """Calculates the time decay factor for a news article."""
    days_old = (datetime.now() - article_date).days
    decay = max(1 - (days_old / 30.0), 0.2)
    return decay

# --- Main Analysis Function ---
def fetch_news_risk(ticker: str, basis: str = "annual"):
    """
    Analyzes news risk using an advanced NLP and weighted scoring model.
    """
    articles = _fetch_google_news(ticker)
    if not articles:
        return {"error": "Could not fetch any news articles for the ticker."}

    sentiment_analyzer = SentimentIntensityAnalyzer()
    headline_scores = []
    risk_headlines = []
    red_flags = 0
    yellow_flags = 0

    for article in articles:
        headline = article['headline']
        risk_weight = 0
        
        # 1. Calculate Base Risk Weighting (R)
        matched_keywords = set()
        for category, data in RISK_EVENT_KEYWORDS.items():
            for keyword in data['keywords']:
                if keyword in headline:
                    risk_weight += 10
                    matched_keywords.add(keyword)
                    if data['flag'] == "Red": red_flags += 1
                    if data['flag'] == "Yellow": yellow_flags += 1
        
        if risk_weight == 0:
            continue # Skip articles with no risk keywords

        # Adjust weight for reputable sources
        if any(source in article['source'] for source in REPUTABLE_SOURCES):
            risk_weight += 2
            
        # 2. Calculate Sentiment Adjustment (S)
        sentiment_score = sentiment_analyzer.polarity_scores(headline)['compound']
        sentiment_adj = 0
        if sentiment_score < -0.5:
            sentiment_adj = 5
        elif sentiment_score > 0.5:
            sentiment_adj = -3

        # 3. Calculate Decay Factor (T)
        decay_factor = _calculate_decay(article['date'])

        # 4. Compute Final Headline Score
        headline_score = (risk_weight * decay_factor) + sentiment_adj
        headline_scores.append(headline_score)
        
        risk_headlines.append({
            "headline": article['headline'].title(),
            "score": round(headline_score, 2),
            "keywords": list(matched_keywords)
        })

    # 5. Compute Total Company Risk Score
    if not headline_scores:
        total_risk_score = 50
    else:
        # Average the scores and normalize to 0-100 scale (capping at 100)
        avg_score = np.mean(headline_scores)
        total_risk_score = min(max(avg_score * 2.5, 0), 100) # Simple scaling, can be refined

    # 6. Determine Verdict (nuanced, descriptive labels)
    if total_risk_score >= 90:
        verdict = "🚨 Extreme Risk: Major negative news or events detected. Exercise maximum caution."
    elif total_risk_score >= 75:
        verdict = "🔴 Very High Risk: Significant negative news or red flags present."
    elif total_risk_score >= 60:
        verdict = "🟠 High Risk: Multiple concerning headlines or ongoing issues."
    elif total_risk_score >= 45:
        verdict = "🟡 Elevated Risk: Some negative news or moderate risk factors."
    elif total_risk_score >= 30:
        verdict = "🟢 Moderate Risk: Mostly stable, but minor concerns exist."
    elif total_risk_score >= 15:
        verdict = "🟦 Low Risk: No major negative news, generally stable."
    else:
        verdict = "🟩 Minimal Risk: No significant risk detected in recent news."

    # Fallback: if no risky headlines, show general headlines and add a note
    if not risk_headlines and articles:
        fallback_headlines = [a['headline'].title() for a in articles[:3]]
        return {
            "risk_score": round(total_risk_score, 2),
            "verdict": verdict,
            "headlines": fallback_headlines,
            "note": "Not much risky headlines found related to the company.",
            "red_flags": red_flags,
            "yellow_flags": yellow_flags
        }
    else:
        return {
            "risk_score": round(total_risk_score, 2),
            "verdict": verdict,
            "headlines": sorted(risk_headlines, key=lambda x: x['score'], reverse=True)[:5], # Top 5 risky headlines
            "red_flags": red_flags,
            "yellow_flags": yellow_flags
        }