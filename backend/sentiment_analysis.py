# backend/sentiment_analysis.py
import requests
import nltk
import logging
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from datetime import datetime, timedelta

# Ensure VADER lexicon is downloaded
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')

def fetch_news_for_sentiment(query: str, max_articles=10):
    url = f"https://news.google.com/rss/search?q={query}+stock&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml-xml')
        items = soup.findAll('item')[:max_articles]
        
        news = []
        for item in items:
            pub_date = None
            if item.pubDate:
                try:
                    pub_date = datetime.strptime(item.pubDate.text, '%a, %d %b %Y %H:%M:%S %Z')
                except (ValueError, TypeError):
                    pass # Ignore if date format is wrong
            news.append({"title": item.title.text.strip(), "date": pub_date})
        return news

    except requests.exceptions.RequestException as e:
        logging.error(f"Google News fetch failed for query '{query}': {e}")
        raise ConnectionError(f"Google News fetch failed: {str(e)}") from e

def analyze_sentiment(ticker: str, basis: str = "annual"):
    try:
        raw_news = fetch_news_for_sentiment(ticker)
        if not raw_news:
            return {"error": "Google News returned no headlines."}

        cutoff_days = 90 if basis.lower() == "quarterly" else 365
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_days)
        
        analyzer = SentimentIntensityAnalyzer()
        scored_headlines = []
        for news in raw_news:
            if news["date"] and news["date"] >= cutoff_date:
                vader_score = analyzer.polarity_scores(news["title"])["compound"]
                blob_score = TextBlob(news["title"]).sentiment.polarity
                avg_score = (vader_score + blob_score) / 2
                scored_headlines.append({"title": news["title"], "score": avg_score})

        if not scored_headlines:
            return {"error": "No recent headlines found for sentiment analysis."}

        total_score = sum(h["score"] for h in scored_headlines)
        avg_score = total_score / len(scored_headlines)
        
        # Scale score from -1 to 1 -> 0 to 10
        sentiment_score = round((avg_score + 1) * 5, 2)
        label = "Positive" if sentiment_score >= 7.0 else "Negative" if sentiment_score < 4.0 else "Neutral"
        
        # Sort by absolute score to show most impactful headlines
        scored_headlines.sort(key=lambda x: abs(x["score"]), reverse=True)

        return {
            "score": sentiment_score,
            "label": label,
            "headlines": scored_headlines[:5]
        }
    
    except ConnectionError as e:
        return {"error": str(e)}
    except Exception as e:
        logging.critical(f"An unexpected error occurred in sentiment analysis for {ticker}: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred during sentiment analysis: {str(e)}"}