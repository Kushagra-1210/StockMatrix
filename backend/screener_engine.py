import yfinance as yf
import numpy as np
from backend.fundamental_analysis import analyze_fundamentals
from backend.technical_analysis import analyze_technical_indicators

def calculate_volatility(ticker: str) -> float:
    try:
        data = yf.Ticker(ticker).history(period="3mo")
        if data.empty or "Close" not in data:
            return None
        returns = data["Close"].pct_change().dropna()
        return round(np.std(returns) * 100, 2)  # percentage std dev
    except Exception:
        return None

def screen_stocks(tickers: list, min_fa: float = 0, min_ta: float = 0, max_volatility: float = 100) -> list:
    results = []

    for ticker in tickers:
        try:
            fa = analyze_fundamentals(ticker)
            ta = analyze_technical_indicators(ticker)
            vol = calculate_volatility(ticker)

            if "error" in fa or "error" in ta or vol is None:
                continue

            if fa["fa_score"] >= min_fa and ta["ta_score"] >= min_ta and vol <= max_volatility:
                results.append({
                    "Ticker": ticker,
                    "FA Score": fa["fa_score"],
                    "TA Score": ta["ta_score"],
                    "Volatility (%)": vol,
                    "FA Verdict": fa["verdict"],
                    "TA Verdict": ta["verdict"]
                })

        except Exception:
            continue

    return sorted(results, key=lambda x: (x["FA Score"] + x["TA Score"]), reverse=True)
