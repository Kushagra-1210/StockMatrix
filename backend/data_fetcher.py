# --- 3D Plot Data Fetcher ---
import yfinance as yf
import requests
import numpy as np

def get_market_data_for_plot(tickers=None):
    """
    Returns a list of dicts: {x: P/E ratio (0-1), y: TA score (0-1), z: Market Cap (0-1), Ticker: symbol}
    Uses Yahoo Finance for primary, FMP for secondary data.
    """
    if tickers is None:
        tickers = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'TSLA']  # Example, replace with your list

    # Fetch data from Yahoo Finance
    pe_ratios = []
    market_caps = []
    ta_scores = []
    results = []
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            info = stock.info
            pe = info.get('trailingPE') or info.get('forwardPE') or 0
            cap = info.get('marketCap') or 0
            # Example TA score: use 50-day MA vs 200-day MA
            hist = stock.history(period='1y')
            ta = 0
            if not hist.empty:
                ma50 = hist['Close'].rolling(50).mean().iloc[-1]
                ma200 = hist['Close'].rolling(200).mean().iloc[-1]
                ta = (ma50 - ma200) / ma200 if ma200 else 0
            pe_ratios.append(pe)
            market_caps.append(cap)
            ta_scores.append(ta)
            results.append({'Ticker': t, 'pe': pe, 'cap': cap, 'ta': ta})
        except Exception:
            # Try FMP as fallback
            try:
                url = f'https://financialmodelingprep.com/api/v3/profile/{t}?apikey=demo'
                resp = requests.get(url)
                if resp.ok:
                    data = resp.json()[0]
                    pe = float(data.get('pe', 0))
                    cap = float(data.get('mktCap', 0))
                    ta = 0  # No TA from FMP in this example
                    pe_ratios.append(pe)
                    market_caps.append(cap)
                    ta_scores.append(ta)
                    results.append({'Ticker': t, 'pe': pe, 'cap': cap, 'ta': ta})
            except Exception:
                continue

    # Normalize
    pe_arr = np.array([r['pe'] for r in results])
    cap_arr = np.array([r['cap'] for r in results])
    ta_arr = np.array([r['ta'] for r in results])
    def norm(arr):
        arr = np.nan_to_num(arr)
        if arr.max() == arr.min():
            return np.zeros_like(arr)
        return (arr - arr.min()) / (arr.max() - arr.min())
    pe_norm = norm(pe_arr)
    cap_norm = norm(cap_arr)
    ta_norm = norm(ta_arr)

    out = []
    for i, r in enumerate(results):
        out.append({
            'x': float(pe_norm[i]),
            'y': float(ta_norm[i]),
            'z': float(cap_norm[i]),
            'Ticker': r['Ticker']
        })
    return out
import yfinance as yf
import pandas as pd
import logging
import time
import streamlit as st
from backend.secondary_data_fetcher import SecondaryDataFetcher

logger = logging.getLogger(__name__)

@st.cache_data(ttl=3600)  # Cache data for 1 hour
def get_ticker_data(ticker_str: str) -> dict:
    """
    Fetch all financial and historical data for a given stock ticker.
    Includes robust exponential backoff for handling rate-limit errors.
    """
    max_retries = 4  # e.g., 5s, 10s, 20s, 40s waits
    initial_retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching all data for {ticker_str} from yfinance (Attempt {attempt + 1})...")
            stock = yf.Ticker(ticker_str)

            # Fetch data sequentially
            info_data = stock.info
            hist_data = stock.history(period="max")
            financials_data = stock.financials
            balance_sheet_data = stock.balance_sheet
            cashflow_data = stock.cashflow

            if hist_data is None or hist_data.empty:
                return {"error": f"No historical price data found for {ticker_str}. Ticker may be invalid or delisted."}

            def to_split_dict(df):
                return df.to_dict('split') if df is not None and not df.empty else {}

            hist_data.reset_index(inplace=True)
            hist_dict = hist_data.to_dict('list') if not hist_data.empty else {}

            fmp_fetcher = SecondaryDataFetcher()
            fmp_data = {
                "income_statement": fmp_fetcher.get_income_statement(ticker_str),
                "balance_sheet": fmp_fetcher.get_balance_sheet_statement(ticker_str),
                "cash_flow": fmp_fetcher.get_cash_flow_statement(ticker_str),
                "key_metrics": fmp_fetcher.get_key_metrics(ticker_str),
                "financial_ratios": fmp_fetcher.get_financial_ratios(ticker_str),
                "company_profile": fmp_fetcher.get_company_profile(ticker_str)
            }

            # If all fetches are successful, return the data
            return {
                "info": info_data or {},
                "history": hist_dict,
                "financials": to_split_dict(financials_data),
                "balance_sheet": to_split_dict(balance_sheet_data),
                "cashflow": to_split_dict(cashflow_data),
                "fmp_data": fmp_data
            }

        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit_error = any(sub in error_msg for sub in ["rate limited", "too many requests", "expecting value"])

            if is_rate_limit_error:
                if attempt < max_retries - 1:
                    delay = initial_retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limit error for {ticker_str}. Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue # Go to the next attempt
                else:
                    logger.error(f"Failed to fetch data for {ticker_str} after {max_retries} attempts due to rate limiting.")
                    return {"error": "The data provider has rate-limited our requests. This is a temporary issue. Please try again later."}
            
            if "no data found" in error_msg or "invalid ticker" in error_msg:
                 return {"error": f"No data found for {ticker_str}. Ticker may be invalid or delisted."}
            
            # For any other unexpected error, fail immediately
            logger.error(f"An unexpected error occurred fetching data for {ticker_str}: {e}", exc_info=True)
            return {"error": f"An unknown error occurred while fetching data: {str(e)}"}
            
    # This line should theoretically not be reached, but as a fallback:
    return {"error": "Failed to fetch data after all retries."}
