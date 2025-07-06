import requests
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from datetime import datetime, timedelta
import streamlit as st  # Import Streamlit

def clean_text(html_text):
    return BeautifulSoup(html_text, "html.parser").get_text()

def expand_url(google_news_url):
    try:
        st.write(f"Expanding URL: {google_news_url}")  # Log the URL being expanded
        resp = requests.get(google_news_url, allow_redirects=True, timeout=5)
        expanded = resp.url
        st.write(f"Expanded URL: {expanded}")  # Log the expanded URL
        return expanded
    except Exception as e:
        st.write(f"URL expand error: {e}")
        return google_news_url

def fetch_news(query: str, max_articles=5):
    url = f"https://news.google.com/rss/search?q={query}+stock&hl=en-IN&gl=IN&ceid=IN:en"
    st.write(f"Fetching news from URL: {url}")  # Log the URL being fetched
    response = requests.get(url)

    try:
        soup = BeautifulSoup(response.content, 'lxml-xml')
    except Exception:
        soup = BeautifulSoup(response.content, 'html.parser')

    items = soup.findAll('item')[:max_articles]
    news = []
    for item in items:
        title = clean_text(item.title.text)
        link = item.link.text  # Directly use the link from the RSS feed

        # Attempt to expand the Google News link if it is a Google News link
        if "google.com" in link:
            expanded_link = expand_url(link)
            if expanded_link:  # If expansion is successful, use it
                link = expanded_link

        # If the link is still empty, log a warning
        if not link:
            st.write(f"Warning: No valid link found for title: {title}")

        pub_date_str = item.pubDate.text if item.pubDate else None
        if pub_date_str:
            try:
                pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %Z')
            except Exception:
                pub_date = None
        else:
            pub_date = None

        news.append({'title': title, 'link': link, 'date': pub_date})  # Ensure 'link' is included

    # Debugging output
    st.write("Fetched news articles:")
    for article in news:
        st.write(f"Title: {article['title']}, Link: {article['link']}")

    return news

def get_sentiment_score(text):
    analyzer = SentimentIntensityAnalyzer()
    vader_score = analyzer.polarity_scores(text)["compound"]
    blob_score = TextBlob(text).sentiment.polarity
    avg_score = (vader_score + blob_score) / 2
    return avg_score

def analyze_sentiment(ticker: str, basis: str = "annual"):
    st.write(f"Sentimental basis = {basis}")
    try:
        headlines = fetch_news(ticker, max_articles=10)
        st.write("Headlines fetched for sentiment analysis:")
        for headline in headlines:
            st.write(f"Title: {headline['title']}, Link: {headline['link']}")

        if not headlines:
            return {"score": 5, "label": "Neutral", "headlines": []}

        cutoff_days = 90 if basis == "quarterly" else 365
        cutoff_date = datetime.utcnow() - timedelta(days=cutoff_days)

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
        st.write(f"Error in analyze_sentiment: {e}")
        return {"error": str(e)}
