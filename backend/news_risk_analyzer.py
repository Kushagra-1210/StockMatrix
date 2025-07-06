import random

def fetch_news_risk(ticker: str, basis: str = "annual") -> dict:
    print(f"News Risk basis = {basis}")

    # Step 1: Define industry-specific headline templates
    industry_headlines = {
        "tech": [
            {"title": f"{ticker} hit by cybersecurity breach", "risk": "High"},
            {"title": f"{ticker} expands into AI R&D", "risk": "Low"},
            {"title": f"{ticker} faces antitrust lawsuit in EU", "risk": "High"},
            {"title": f"{ticker} launches new product line", "risk": "Low"},
            {"title": f"{ticker} loses cloud contract to rival", "risk": "Medium"},
            {"title": f"{ticker} reports chip shortage impact", "risk": "Medium"},
            {"title": f"{ticker} stock surges after keynote event", "risk": "Low"},
            {"title": f"{ticker} faces employee union protests", "risk": "Medium"},
            {"title": f"{ticker} under investigation for data misuse", "risk": "High"},
        ],
        "finance": [
            {"title": f"{ticker} under SEC investigation", "risk": "High"},
            {"title": f"{ticker} beats earnings estimates", "risk": "Low"},
            {"title": f"{ticker} reports bad loan exposure", "risk": "Medium"},
            {"title": f"{ticker} announces 5% workforce layoffs", "risk": "Medium"},
            {"title": f"{ticker} wins fintech innovation award", "risk": "Low"},
            {"title": f"{ticker} hit by bond market volatility", "risk": "Medium"},
            {"title": f"{ticker} faces liquidity pressure from short sellers", "risk": "High"},
            {"title": f"{ticker} stock rallies on interest rate outlook", "risk": "Low"},
        ],
        "retail": [
            {"title": f"{ticker} hit by falling consumer demand", "risk": "High"},
            {"title": f"{ticker} launches global e-commerce platform", "risk": "Low"},
            {"title": f"{ticker} facing inflationary supply cost pressures", "risk": "Medium"},
            {"title": f"{ticker} recalls product after safety concerns", "risk": "High"},
            {"title": f"{ticker} reports record holiday season sales", "risk": "Low"},
            {"title": f"{ticker} sees slow growth in emerging markets", "risk": "Medium"},
        ]
    }

    # Step 2: Guess sector (naive approach for now)
    ticker_lower = ticker.lower()
    if any(word in ticker_lower for word in ["bank", "fin", "nbfc", "hdfc", "icici", "sbi"]):
        sector = "finance"
    elif any(word in ticker_lower for word in ["tech", "infy", "tcs", "msft", "apple", "meta", "goog", "it"]):
        sector = "tech"
    elif any(word in ticker_lower for word in ["reliance", "dmart", "retail", "shop", "cost", "wmt"]):
        sector = "retail"
    else:
        # Fallback if unknown
        sector = random.choice(["tech", "finance", "retail"])

    headlines_pool = industry_headlines.get(sector, industry_headlines["tech"])
    selected_news = random.sample(headlines_pool, 3)

    # Step 3: Score logic
    risk_score = sum(
        10 if n["risk"] == "High" else 5 if n["risk"] == "Medium" else 0 for n in selected_news
    )
    risk_score_normalized = round(100 - (risk_score / 30) * 100, 2)

    verdict = (
        "Safe" if risk_score_normalized >= 70 else
        "Watch" if risk_score_normalized >= 50 else
        "Risky"
    )

    return {
        "news": selected_news,
        "risk_score": risk_score_normalized,
        "verdict": verdict
    }
