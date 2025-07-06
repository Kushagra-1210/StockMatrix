import requests
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob
from datetime import datetime, timedelta

def clean_text(html_text):
    return BeautifulSoup(html_text, "html.parser").get_text()

def expand_url(google_news_url):
    try:
        resp = requests.get(google_news_url, allow_redirects=True, timeout=5)
        expanded = resp.url
        print(f"Expanded URL: {expanded}")  # Log to console
        return expanded
    except Exception as e:
        print(f"URL expand error: {e}")
        return google_news_url

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

        # Check if the link is a Google News link and modify it to point to the actual article
        if "google.com" in link:
            # Extract the actual article link from the description
            description = clean_text(item.description.text)
            start_index = description.find('href="') + len('href="')
            end_index = description.find('"', start_index)
            if start_index != -1 and end_index != -1:
                link = description[start_index:end_index]

        # Expand Google News redirect URL to actual article URL
        link = expand_url(link)

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
    print("Fetched news articles:")
    for article in news:
        print(f"Title: {article['title']}, Link: {article['link']}")

    return news

def get_sentiment_score(text):
    analyzer = SentimentIntensityAnalyzer()
    vader_score = analyzer.polarity_scores(text)["compound"]
    blob_score = TextBlob(text).sentiment.polarity
    avg_score = (vader_score + blob_score) / 2
    return avg_score

def analyze_sentiment(ticker: str, basis: str = "annual"):
    print(f"Sentimental basis = {basis}")
    try:
        headlines = fetch_news(ticker, max_articles=10)
        print("Headlines fetched for sentiment analysis:")
        for headline in headlines:
            print(f"Title: {headline['title']}, Link: {headline['link']}")

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
        return {"error": str(e)}
