import yfinance as yf
import requests
import logging
from bs4 import BeautifulSoup
import nltk
import nltk.downloader # Explicitly import the submodule
from datetime import datetime

# Ensure NLTK data is available
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except nltk.downloader.DownloadError:
    nltk.download('vader_lexicon')

from nltk.sentiment.vader import SentimentIntensityAnalyzer
from backend.secondary_data_fetcher import SecondaryDataFetcher # Import the FMP fetcher

logger = logging.getLogger(__name__)

# --- PART A: Market Sentiment Score ---
def get_market_sentiment_score(ticker: str):
    """
    Fetches Google News headlines and calculates a sentiment score from 0-10.
    """
    try:
        url = f"https://news.google.com/rss/search?q={ticker}+stock+market&hl=en-US&gl=US&ceid=US:en"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'xml')
        headlines = [item.title.text.strip() for item in soup.findAll('item')[:20]]

        if not headlines:
            return 5.0, ["No market news found."]

        analyzer = SentimentIntensityAnalyzer()
        scores = [analyzer.polarity_scores(h)['compound'] for h in headlines]
        
        # Normalize compound score (-1 to 1) to a 0-10 scale
        # (score + 1) -> maps to 0-2 range
        # * 5 -> maps to 0-10 range
        sentiment_score = (sum(scores) / len(scores) + 1) * 5
        
        return sentiment_score, headlines

    except Exception as e:
        logger.error(f"Error calculating market sentiment score for {ticker}: {e}")
        return 5.0, ["Error calculating market sentiment score"]

# --- PART B: Management Quality Score (NOW WITH REAL DATA) ---
def get_management_quality_score(ticker: str, info: dict):
    """
    Calculates a management quality score (0-10) using real governance data from FMP.
    """
    notes = []
    fmp_fetcher = SecondaryDataFetcher()
    governance_data = fmp_fetcher._make_request(f"governance/{ticker}")

    # --- Default scores if API fails ---
    ceo_score = 0.75
    board_score = 0.75
    
    if governance_data:
        # 1. CEO Tenure -> Score 0-2
        ceo_tenure_years = 0
        for exec in governance_data:
            if exec.get('title') and ('chief executive officer' in exec['title'].lower() or 'ceo' in exec['title'].lower()):
                tenure_since = exec.get('since')
                if tenure_since:
                    try:
                        ceo_tenure_years = (datetime.now().year - int(tenure_since))
                        if ceo_tenure_years > 10:
                            ceo_score = 2.0 # Long, stable leadership
                        elif ceo_tenure_years > 3:
                            ceo_score = 1.5 # Established leader
                        else:
                            ceo_score = 0.5 # New leader, potential instability
                        notes.append(f"CEO tenure: {ceo_tenure_years} years.")
                    except (ValueError, TypeError):
                        notes.append("Could not parse CEO tenure date.")
                break # Found the CEO
        
        # 2. Board Independence -> Score 0-2
        board_members = governance_data
        if board_members:
            independent_directors = sum(1 for member in board_members if member.get('independent_director', False))
            total_directors = len(board_members)
            independence_pct = (independent_directors / total_directors) * 100 if total_directors > 0 else 0
            
            if independence_pct > 75:
                board_score = 2.0 # Highly independent
            elif independence_pct > 50:
                board_score = 1.5 # Majority independent
            else:
                board_score = 0.5 # Lacks independent oversight
            notes.append(f"Board independence: {independence_pct:.1f}%.")
        else:
            notes.append("Board composition data not available.")
    else:
        notes.append("Governance data not available via FMP, using neutral scores.")

    # 3. Insider Holding (%) -> Score 0-2 (from yfinance)
    held_pct_insiders = info.get('heldPercentInsiders', 0) * 100
    insider_score = 2 if held_pct_insiders > 15 else (held_pct_insiders / 15) * 2
    if held_pct_insiders > 0:
        notes.append(f"Insider holdings: {held_pct_insiders:.1f}%.")

    # 4. Executive Compensation vs EPS -> Score 0-2 (from yfinance)
    total_comp = info.get('totalPay', {}).get('raw', 0) if info.get('companyOfficers') else 0
    trailing_eps = info.get('trailingEps', 0)
    comp_vs_eps_score = 1.0 # Start neutral
    if total_comp > 15_000_000 and trailing_eps < 1.0:
        comp_vs_eps_score = 0
        notes.append("Note: High executive compensation relative to low EPS.")
    elif total_comp < 10_000_000 and trailing_eps > 3.0:
        comp_vs_eps_score = 2
        notes.append("Note: Reasonable executive compensation relative to high EPS.")

    # Sum all scores and normalize to a 0-10 scale
    # Max possible raw score is 2(CEO) + 2(Board) + 2(Insider) + 2(Comp) = 8
    raw_total = ceo_score + board_score + insider_score + comp_vs_eps_score
    final_score = (raw_total / 8) * 10

    return max(0, min(10, final_score)), notes


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
        verdict = "✅ Strong Perception: Market and management sentiment are highly positive."
    elif total_score > 10:
        verdict = "🟢 Positive Perception: Generally favorable sentiment with minor concerns."
    elif total_score > 6:
        verdict = "🟡 Neutral Perception: Mixed or balanced sentiment."
    elif total_score > 3:
        verdict = "� Cautious Perception: Some negative sentiment or red flags present."
    else:
        verdict = "🔴 Negative Perception: Predominantly negative sentiment detected."

    sample_headlines = headlines[:5] if isinstance(headlines, list) else []

    result = {
        "score": round(total_score / 2, 2),
        "strategic_perception_score": round(total_score, 2),
        "verdict": verdict,
        "market_sentiment_score": round(market_score, 2),
        "management_quality_score": round(mgmt_score, 2),
        "sample_headlines": sample_headlines,
        "management_notes": mgmt_notes
    }
    return result
