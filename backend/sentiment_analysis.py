import requests
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from datetime import datetime, timedelta

def clean_text(html_text):
    return BeautifulSoup(html_text, "html.parser").get_text()


def fetch_news(query: str, max_articles=10):
    url = f"https://news.google.com/rss/search?q={query}+stock&hl=en-IN&gl=IN&ceid=IN:en"
    response = requests.get(url)

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


def get_label_and_color(score):
    if score >= 0.3:
        return "🟢 Positive", "green"
    elif score > -0.3:
        return "🟡 Neutral", "orange"
    else:
        return "🔴 Negative", "red"


def analyze_sentiment(ticker: str, basis: str = "annual"):
    try:
        headlines = fetch_news(ticker, max_articles=10)

        if not headlines:
            return {"score": 5, "label": "Neutral", "headlines": []}

        # Filter based on Quarterly/Annual cutoff
        cutoff_days = 90 if basis.lower() == "quarterly" else 365
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_days)
        filtered = [n for n in headlines if n.get("date") and n["date"] >= cutoff_date]

        if not filtered:
            return {"score": 5, "label": "Neutral", "headlines": []}

        scored_headlines = []
        for news in filtered:
            score = get_sentiment_score(news["title"])
            scored_headlines.append({
                "title": news["title"],
                "score": round(score, 3),
                "date": news["date"]
            })

        # Sort and select top 5 by absolute sentiment
        scored_headlines.sort(key=lambda x: abs(x["score"]), reverse=True)
        top_5 = scored_headlines[:5]

        # Add label and color to top 5
        total_score = 0
        for h in top_5:
            label, color = get_label_and_color(h["score"])
            h["label"] = label
            h["color"] = color
            total_score += h["score"]

        avg_score = total_score / len(top_5)
        sentiment_score = round((avg_score + 1) * 5, 2)

        # Overall sentiment label
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
        return {"error": str(e)}
