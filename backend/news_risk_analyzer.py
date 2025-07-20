import yfinance as yf
import numpy as np
import logging
from backend.fundamental_analysis import analyze_fundamentals
from backend.technical_analysis import analyze_technical_indicators

def calculate_volatility(ticker: str) -> float:
    try:
        data = yf.Ticker(ticker).history(period="3mo")
        if data.empty or "Close" not in data:
            return None
        returns = data["Close"].pct_change().dropna()
        if returns.empty:
            return None
        return round(np.std(returns) * 100, 2)
    except Exception as e:
        logging.warning(f"Could not calculate volatility for {ticker}: {e}")
        return None

def screen_stocks(tickers: list, min_fa: float = 0, min_ta: float = 0, max_volatility: float = 100, basis: str = "annual") -> list:
    results = []

    for ticker in tickers:
        try:
            fa = analyze_fundamentals(ticker, basis=basis)
            ta = analyze_technical_indicators(ticker, basis=basis)
            vol = calculate_volatility(ticker)

            if any(isinstance(r, dict) and "error" in r for r in [fa, ta]) or vol is None:
                logging.warning(f"Skipping {ticker} in screener due to analysis error or missing volatility.")
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

        except KeyError as e:
            logging.error(f"Screener failed for {ticker} due to missing data key: {e}. Skipping.")
            continue
        except Exception as e:
            logging.critical(f"An unexpected error occurred in screener for {ticker}: {e}", exc_info=True)
            continue

    return sorted(results, key=lambda x: (x["FA Score"] + x["TA Score"]), reverse=True)