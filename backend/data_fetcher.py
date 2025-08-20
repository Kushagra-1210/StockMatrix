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
