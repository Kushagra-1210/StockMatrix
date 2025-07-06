import requests
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from datetime import datetime, timedelta
import streamlit as st


def clean_text(html_text):
    return BeautifulSoup(html_text, "html.parser").get_text()


def fetch_news(query: str, max_articles=5):
    url = f"https://news.google.com/rss/search?q={query}+stock&hl=en-IN&gl=IN&ceid=IN:en"
    st.write(f"📡 Fetching news from URL: {url}")
    
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

        if pub_date_str:
            try:
                pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %Z')
            except Exception:
                pub_date = None
        else:
            pub_date = None

        if title:
            news.append({
                "title": title,
                "date": pub_date
            })

    st.write("📰 Headlines fetched:")
    for n in news:
        st.write(f"- {n['title']}")

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
    st.write(f"🧠 Sentiment analysis basis: **{basis}**")

    try:
        headlines = fetch_news(ticker, max_articles=10)

        if not headlines:
            return {"score": 5, "label": "Neutral", "headlines": []}

        cutoff_days = 90 if basis.lower() == "quarterly" else 365
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_days)
        filtered = [n for n in headlines if n.get("date") and n["date"] >= cutoff_date]

        if not filtered:
            return {"score": 5, "label": "Neutral", "headlines": []}

        total_score = 0
        result_headlines = []

        for news in filtered:
            score = get_sentiment_score(news["title"])
            label, color = get_label_and_color(score)

            news_data = {
                "title": news["title"],
                "score": round(score, 3),
                "date": news["date"],
                "label": label,
                "color": color
            }

            total_score += score
            result_headlines.append(news_data)

        result_headlines.sort(key=lambda x: abs(x["score"]), reverse=True)

        avg_score = total_score / len(result_headlines)
        sentiment_score = round((avg_score + 1) * 5, 2)

        overall_label = (
            "Positive" if sentiment_score >= 6.5 else
            "Neutral" if sentiment_score >= 4 else
            "Negative"
        )

        # Display in Streamlit
        st.markdown("### 🧠 Sentiment Headlines (Sorted)")
        for item in result_headlines:
            st.markdown(
                f"<span style='color:{item['color']}'><b>{item['label']}</b></span>: {item['title']}",
                unsafe_allow_html=True
            )

        return {
            "score": sentiment_score,
            "label": overall_label,
            "headlines": result_headlines
        }

    except Exception as e:
        st.write(f"❌ Error in analyze_sentiment: {e}")
        return {"error": str(e)}
