# backend/sentiment_analysis.py
import requests
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from transformers import BertTokenizer, BertForSequenceClassification, pipeline

logger = logging.getLogger(__name__)

# --- 1. Initialize the FinBERT Model (will download on first run) ---
# This is a one-time setup that loads the pre-trained financial model
try:
    finbert = BertForSequenceClassification.from_pretrained('yiyanghkust/finbert-tone')
    tokenizer = BertTokenizer.from_pretrained('yiyanghkust/finbert-tone')
    nlp_pipeline = pipeline("sentiment-analysis", model=finbert, tokenizer=tokenizer)
except Exception as e:
    logger.error(f"Failed to load FinBERT model: {e}. Sentiment analysis will not be available.")
    nlp_pipeline = None

# --- 2. Data Collection Functions ---

def _fetch_market_news(ticker: str, max_articles=15):
    """Fetches external market news headlines from Google News RSS."""
    headlines = []
    try:
        url = f"https://news.google.com/rss/search?q={ticker}+stock+market&hl=en-US&gl=US&ceid=US:en"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.findAll('item')[:max_articles]
        for item in items:
            headlines.append(item.title.text.strip())
        return headlines
    except Exception as e:
        logger.error(f"Failed to fetch market news for {ticker}: {e}")
        return headlines # Return any headlines fetched so far

def _fetch_earnings_transcript(ticker: str, api_key: str):
    """
    Fetches the most recent earnings call transcript from Financial Modeling Prep.
    NOTE: This is a premium feature on FMP, but we include the logic here.
    """
    transcript_text = ""
    try:
        # This API endpoint often requires a paid FMP plan.
        url = f"https://financialmodelingprep.com/api/v3/earning_call_transcript/{ticker}?quarter=1&year={datetime.now().year}&apikey={api_key}"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data and 'content' in data[0]:
            transcript_text = data[0]['content']
        return transcript_text
    except Exception as e:
        logger.warning(f"Could not fetch earnings transcript for {ticker} (premium feature?): {e}")
        return transcript_text

# --- 3. Sentiment Scoring and Aggregation ---

def _get_sentiment_score(text_list: list) -> float:
    """
    Analyzes a list of text snippets with FinBERT and returns a single score.
    The score is (Positive % - Negative %) scaled to a -10 to +10 range.
    """
    if not nlp_pipeline or not text_list:
        return 0.0

    results = nlp_pipeline(text_list)
    
    positive_count = 0
    negative_count = 0
    
    for r in results:
        label = r['label'].lower()
        if label == 'positive':
            positive_count += 1
        elif label == 'negative':
            negative_count += 1
            
    total = len(results)
    if total == 0:
        return 0.0
        
    positive_pct = positive_count / total
    negative_pct = negative_count / total
    
    # Final score: (% Positive - % Negative) scaled to 10
    score = (positive_pct - negative_pct) * 10
    return score

# --- 4. Main Analysis Function ---

def analyze_sentiment(ticker: str, fmp_api_key: str = None):
    """
    Performs a combined sentiment analysis using FinBERT on market and internal data.
    """
    if not nlp_pipeline:
        return {"error": "FinBERT model is not available."}

    # --- Market Sentiment (External) ---
    market_headlines = _fetch_market_news(ticker)
    if not market_headlines:
        notes = ["Could not fetch market news."]
        market_score = 0.0
    else:
        notes = []
        market_score = _get_sentiment_score(market_headlines)
        
    # --- Internal Sentiment (Earnings Call) ---
    # This part is optional and depends on having a valid FMP API key for the premium endpoint
    internal_score = 0.0 # Default to neutral if no transcript is available
    if fmp_api_key:
        transcript = _fetch_earnings_transcript(ticker, fmp_api_key)
        if transcript:
            # Chunk the transcript into smaller pieces for the model
            transcript_chunks = [transcript[i:i+512] for i in range(0, len(transcript), 512)]
            internal_score = _get_sentiment_score(transcript_chunks)
        else:
            notes.append("Earnings call transcript not available.")
    else:
        notes.append("FMP API key not provided; skipping internal sentiment analysis.")

    # --- 5. Weighted Aggregation and Verdict ---
    final_score = (0.6 * market_score) + (0.4 * internal_score)

    # Normalize final score to a 0-100 scale for consistency with other modules
    # Maps the -10 to +10 range to a 0 to 100 range
    final_score_100 = (final_score + 10) * 5
    
    if final_score >= 5: verdict = "Positive Outlook"
    elif final_score <= -5: verdict = "Negative Outlook"
    else: verdict = "Neutral"

    return {
        "score": round(final_score_100, 2),
        "label": verdict,
        "market_sentiment_score": round(market_score, 2),
        "internal_sentiment_score": round(internal_score, 2),
        "notes": notes
    }