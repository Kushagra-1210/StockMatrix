import requests 
import requests

def expand_url(google_news_url):
    try:
        resp = requests.get(google_news_url, allow_redirects=True, timeout=5)
        return resp.url
    except Exception:
        return google_news_url

from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from datetime import datetime, timedelta

def clean_text(html_text):
    return BeautifulSoup(html_text, "html.parser").get_text()

def expand_url(google_news_url):
    try:
        resp = requests.get(google_news_url, allow_redirects=True, timeout=5)
        return resp.url
    except Exception:
        return google_news_url  # fallback to original link if error

def fetch_news(query: str, max_articles=5):
    url = f"https://news.google.com/rss/search?q={query}+stock&hl=en-IN&gl=IN&ceid=IN:en"
    response = requests.get(url)

    try:
        soup = BeautifulSoup(response.content, 'lxml-xml')
    except Exception:
        soup = BeautifulSoup(response.content, 'html.parser')

    items = soup.findAll('item')[:max_articles]
    news = []
    for item in items:
        title = clean_text(item.title.text)
        link = item.link.text
        if link.startswith("/"):
            link = "https://news.google.com" + link  # Convert to full URL

        # Expand Google News redirect URL to original URL
        link = expand_url(link)

        # Parse pubDate
        pub_date_str = item.pubDate.text if item.pubDate else None
        if pub_date_str:
            try:
                pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %Z')
            except Exception:
                pub_date = None
        else:
            pub_date = None

        news.append({'title': title, 'link': link, 'date': pub_date})
    return news

def get_sentiment_score(text):
    analyzer = SentimentIntensityAnalyzer()
    vader_score = analyzer.polarity_scores(text)["compound"]
    blob_score = TextBlob(text).sentiment.polarity
    avg_score = (vader_score + blob_score) / 2
    return avg_score

def analyze_sentiment(ticker: str, basis: str = "annual"):
    try:
        headlines = fetch_news(ticker, max_articles=10)
        if not headlines:
            return {"score": 5, "label": "Neutral", "headlines": []}

        # Time filter
        cutoff_days = 90 if basis == "quarterly" else 365
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_days)

        # Filter headlines which have valid date and date >= cutoff_date
        filtered = [n for n in headlines if n.get("date") and n["date"] >= cutoff_date]

        if not filtered:
            return {"score": 5, "label": "Neutral", "headlines": []}

        total_score = 0
        for news in filtered:
            score = get_sentiment_score(news["title"])
            news["score"] = round(score, 3)
            total_score += score

        avg_score = total_score / len(filtered)
        sentiment_score = round((avg_score + 1) * 5, 2)  # Normalize -1 to 1 → 0 to 10

        if sentiment_score >= 6.5:
            label = "Positive"
        elif sentiment_score >= 4:
            label = "Neutral"
        else:
            label = "Negative"

        return {
            "score": sentiment_score,
            "label": label,
            "headlines": filtered
        }

    except Exception as e:
        return {"error": str(e)}
