import requests
import nltk
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from datetime import datetime, timedelta

try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')


def clean_text(html_text):
    return BeautifulSoup(html_text, "html.parser").get_text()


def fetch_news(query: str, max_articles=10):
    url = f"https://news.google.com/rss/search?q={query}+stock&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except requests.RequestException as e:
        return {"error": f"Google News fetch failed: {str(e)}"}

    try:
        soup = BeautifulSoup(response.content, 'lxml-xml')
    except Exception:
        soup = BeautifulSoup(response.content, 'html.parser')

    items = soup.findAll('item')[:max_articles]
    news = []

    for item in items:
        title = clean_text(item.title.text).strip()
        pub_date_str = item.pubDate.text if item.pubDate else None
        pub_date = None
        if pub_date_str:
            try:
                pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %Z')
            except Exception:
                pass
        if title:
            news.append({
                "title": title,
                "date": pub_date
            })

    return news


def get_sentiment_score(text):
    analyzer = SentimentIntensityAnalyzer()
    vader_score = analyzer.polarity_scores(text)["compound"]
    blob_score = TextBlob(text).sentiment.polarity
    avg_score = (vader_score + blob_score) / 2
    return avg_score


def get_label(score):
    if score >= 0.3:
        return "🟢 Positive"
    elif score > -0.3:
        return "🟡 Neutral"
    else:
        return "🔴 Negative"


def analyze_sentiment(ticker: str, basis: str = "annual"):
    try:
        raw_news = fetch_news(ticker, max_articles=10)
        if isinstance(raw_news, dict) and raw_news.get("error"):
            return {
                "score": 5,
                "label": "Neutral",
                "headlines": [],
                "error": raw_news["error"]
            }

        headlines = raw_news
        if not headlines:
            return {
                "score": 5,
                "label": "Neutral",
                "headlines": [],
                "error": "Google News returned no headlines. Default neutral sentiment applied."
            }

        # Filter based on Quarterly/Annual cutoff
        cutoff_days = 90 if basis.lower() == "quarterly" else 365
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_days)
        filtered = [n for n in headlines if n.get("date") and n["date"] >= cutoff_date]

        if not filtered:
            return {
                "score": 5,
                "label": "Neutral",
                "headlines": [],
                "error": "No recent headlines found. Default neutral sentiment applied."
            }

        scored_headlines = []
        for news in filtered:
            score = get_sentiment_score(news["title"])
            scored_headlines.append({
                "title": news["title"],
                "score": round(score, 3),
                "label": get_label(score),
                "date": news["date"]
            })

        # Sort by sentiment strength
        scored_headlines.sort(key=lambda x: abs(x["score"]), reverse=True)
        top_5 = scored_headlines[:5]

        if not top_5:
            return {
                "score": 5,
                "label": "Neutral",
                "headlines": [],
                "error": "No strong sentiment found. Default neutral applied."
            }

        total_score = sum(h["score"] for h in top_5)
        avg_score = total_score / len(top_5)
        sentiment_score = round((avg_score + 1) * 5, 2)

        if sentiment_score >= 6.5:
            label = "Positive"
        elif sentiment_score >= 4:
            label = "Neutral"
        else:
            label = "Negative"

        return {
            "score": sentiment_score,
            "label": label,
            "headlines": top_5
        }

    except Exception as e:
        return {
            "score": 5,
            "label": "Neutral",
            "headlines": [],
            "error": f"Sentiment analysis error: {str(e)}"
        }
