import yfinance as yf
import requests
import logging
from bs4 import BeautifulSoup
from textblob import TextBlob
import nltk
nltk.download('vader_lexicon')
from nltk.sentiment.vader import SentimentIntensityAnalyzer
logger = logging.getLogger(__name__)

# --- Main Orchestrator Function ---
def get_market_sentiment_score(ticker: str):
    """
    Fetches Google News headlines and calculates a sentiment score from 0-10.
    """
    try:
        # 1. Fetch Google News RSS
        url = f"https://news.google.com/rss/search?q={ticker}+stock+market&hl=en-US&gl=US&ceid=US:en"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'xml')
        headlines = [item.title.text.strip() for item in soup.findAll('item')[:20]]

        if not headlines:
            return 5.0, ["No market news found."] # Return neutral score

        # 2. Run VADER Sentiment Analysis
        analyzer = SentimentIntensityAnalyzer()
        positive_count, neutral_count, negative_count = 0, 0, 0
        # Error was happening because TextBlob was not installed
        # Fixed by adding `python -m textblob.download_corpora` to Dockerfile
        negative_headlines = []

        for headline in headlines:
            blob = TextBlob(headline)
            sentiment = blob.sentiment

            # Check for neutral sentiment scores
            if abs(sentiment.polarity) < 0.1:
                neutral_count += 1
            elif sentiment.polarity > 0:
                positive_count += 1
            elif sentiment.polarity < 0:
                negative_count += 1
                negative_headlines.append(headline)

        # Calculate sentiment score
        sentiment_score = (positive_count - negative_count) / len(headlines) * 10

        return sentiment_score, negative_headlines

    except Exception as e:
        logger.error(f"Error calculating market sentiment score: {e}")
        return 5.0, ["Error calculating market sentiment score"]

# --- Other functions remain the same ---

# --- PART B: Management Quality Score ---

def get_management_quality_score(ticker: str, info: dict):
    """
    Calculates a management quality score (0-10) based on governance metrics.
    """
    try:
        notes = []
        # 1. Insider Holding (%) -> Score 0-2
        held_pct_insiders = info.get('heldPercentInsiders', 0) * 100
        insider_score = 2 if held_pct_insiders > 15 else (held_pct_insiders / 15) * 2

        # 2. CEO Tenure -> Score 0-1.5 (This data is not available in yfinance, so we use a neutral default)
        ceo_score = 0.75 
        notes.append("CEO tenure data not available via yfinance, using neutral score.")

        # 3. Board Independence -> Score 0-1.5 (Not available, use neutral default)
        board_score = 0.75
        notes.append("Board independence data not available, using neutral score.")

        # 4. Auditor Change Frequency -> Score 0-1 (Not available, use neutral default)
        auditor_score = 0.5
        notes.append("Auditor change data not available, using neutral score.")

        # 5. Governance Red Flags -> Score 0-2 (Based on news, a more complex integration)
        # For simplicity, we assume no red flags unless a more advanced news scan is built.
        red_flag_penalty = 0 # This would be a negative score

        # 6. Executive Compensation vs EPS -> Score 0-2
        total_comp = info.get('totalPay', {}).get('raw', 0) if info.get('companyOfficers') else 0
        trailing_eps = info.get('trailingEps', 0)
        comp_vs_eps_score = 1.0 # Start neutral
        if total_comp > 15_000_000 and trailing_eps < 1.0: # Example logic: High comp, low EPS
            comp_vs_eps_score = 0
        elif total_comp < 10_000_000 and trailing_eps > 3.0: # Example logic: Reasonable comp, high EPS
            comp_vs_eps_score = 2

        # Sum all scores and normalize to a 0-10 scale
        raw_total = insider_score + ceo_score + board_score + auditor_score + red_flag_penalty + comp_vs_eps_score
        # Max possible score is 2 + 1.5 + 1.5 + 1 + 0 + 2 = 8
        final_score = (raw_total / 8) * 10

        return max(0, min(10, final_score)), notes

    except Exception as e:
        logger.error(f"Management quality analysis failed for {ticker}: {e}")
        return 5.0, [f"An error occurred: {e}"] # Return neutral score on error

# --- Main Orchestrator Function ---
from backend.data_fetcher import get_ticker_data

def analyze_perception(ticker: str):
    """
    Runs the full Strategic Perception Analysis using centralized data fetcher.
    """
    ticker_data = get_ticker_data(ticker)
    info = ticker_data.get("info", {})

    # Get scores from both parts
    market_score, headlines = get_market_sentiment_score(ticker)
    mgmt_score, mgmt_notes = get_management_quality_score(ticker, info)

    # Combine for final score (out of 20)
    total_score = market_score + mgmt_score

    # Determine verdict
    if total_score > 16:
        verdict = "🌟 Strong Perception: Market and management sentiment are highly positive."
    elif total_score > 10:
        verdict = "🟢 Positive Perception: Generally favorable sentiment with minor concerns."
    elif total_score > 6:
        verdict = "🟡 Neutral Perception: Mixed or balanced sentiment."
    elif total_score > 3:
        verdict = "🟠 Cautious Perception: Some negative sentiment or red flags present."
    else:
        verdict = "🔴 Negative Perception: Predominantly negative sentiment detected."

    # If headlines is a dict (fallback), unpack for UI compatibility
    sample_headlines = headlines["headlines"] if isinstance(headlines, dict) else headlines
    note = headlines.get("note") if isinstance(headlines, dict) else None

    result = {
        "score": round(total_score / 2, 2),  # Add a 'score' out of 10 for compatibility
        "strategic_perception_score": round(total_score, 2),
        "verdict": verdict,
        "market_sentiment_score": round(market_score, 2),
        "management_quality_score": round(mgmt_score, 2),
        "sample_headlines": sample_headlines,
        "management_notes": mgmt_notes
    }
    if note:
        result["note"] = note
    return result