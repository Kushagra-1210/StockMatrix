# backend/sentiment_analysis.py
import yfinance as yf
import requests
import logging
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

# --- PART A: Market Sentiment Score ---

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
        for h in headlines:
            score = analyzer.polarity_scores(h)['compound']
            if score >= 0.05:
                positive_count += 1
            elif score <= -0.05:
                negative_count += 1
            else:
                neutral_count += 1
        
        total = len(headlines)
        
        # 3. Aggregate to 0-10 scale
        score = (positive_count - negative_count + neutral_count * 0.5) / total * 10
        return max(0, min(10, score)), headlines[:3] # Clamp score between 0-10

    except Exception as e:
        logger.error(f"Market sentiment analysis failed for {ticker}: {e}")
        return 5.0, [f"Failed to fetch news: {e}"] # Return neutral score on error

# --- PART B: Management Quality Score ---

def get_management_quality_score(ticker: str, stock: yf.Ticker):
    """
    Calculates a management quality score (0-10) based on governance metrics.
    """
    try:
        info = stock.info
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
def analyze_perception(ticker: str):
    """
    Runs the full Strategic Perception Analysis.
    """
    stock = yf.Ticker(ticker)
    
    # Get scores from both parts
    market_score, headlines = get_market_sentiment_score(ticker)
    mgmt_score, mgmt_notes = get_management_quality_score(ticker, stock)
    
    # Combine for final score (out of 20)
    total_score = market_score + mgmt_score
    
    # Determine verdict
    if total_score > 16: verdict = "Strong Perception"
    elif total_score > 10: verdict = "Positive Perception"
    else: verdict = "Negative Perception"
        
    return {
        "score": round(total_score / 2, 2),  # Add a 'score' out of 10 for compatibility
        "strategic_perception_score": round(total_score, 2),
        "verdict": verdict,
        "market_sentiment_score": round(market_score, 2),
        "management_quality_score": round(mgmt_score, 2),
        "sample_headlines": headlines,
        "management_notes": mgmt_notes
    }