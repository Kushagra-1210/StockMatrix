import yfinance as yf
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import time

logger = logging.getLogger(__name__)

@st.cache_data(ttl=3600)  # Cache data for 1 hour
def get_ticker_data(ticker_str: str) -> dict:
    """
    Fetch all financial and historical data for a given stock ticker using yfinance.
    Includes validation to ensure data isn't empty and logs meaningful errors.
    """
    max_retries = 3
    retry_delay = 60  # seconds

    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching all data for {ticker_str} from yfinance...")
            stock = yf.Ticker(ticker_str)

            # Fetch data sequentially to avoid rate-limiting from too many parallel requests.
            info_data = stock.info
            hist_data = stock.history(period="max")
            financials_data = stock.financials
            balance_sheet_data = stock.balance_sheet
            cashflow_data = stock.cashflow

            # Validate data availability
            if hist_data is None or hist_data.empty:
                return {"error": f" No historical price data found for {ticker_str}. Ticker may be invalid or delisted."}

            # --- CRITICAL CHANGE: Save the date index to a column ---
            hist_data.reset_index(inplace=True)

            if not info_data:
                return {"error": f" No company info found for {ticker_str}. Ticker may be invalid or restricted."}

            # Convert data to a robust serializable format
            return {
                "info": info_data or {},
                "history": hist_data.to_dict('list') if not hist_data.empty else {},
                "financials": financials_data.to_dict('list') if not financials_data.empty else {},
                "balance_sheet": balance_sheet_data.to_dict('list') if not balance_sheet_data.empty else {},
                "cashflow": cashflow_data.to_dict('list') if not cashflow_data.empty else {},
            }

        except yf.TickerError as e:
            logger.error(f"Error fetching data for {ticker_str}: {e}")
            error_msg = str(e)
            if "No data found" in error_msg:
                return {"error": f" No data found for {ticker_str}. Ticker may be invalid or delisted."}
            elif "Invalid ticker symbol" in error_msg:
                return {"error": f" Invalid ticker symbol: {ticker_str}"}
            else:
                return {"error": f" Unknown error fetching data for {ticker_str}: {error_msg}"}

        except Exception as e:
            logger.error(f"Error fetching data for {ticker_str}: {e}")
            error_msg = str(e)
            if "Rate limited" in error_msg or "Too Many Requests" in error_msg:
                if attempt < max_retries - 1:
                    logger.info(f"Rate limit error. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    error_msg = "The data provider (Yahoo Finance) has rate-limited our requests. This is a temporary error. Please try again later."
                    return {"error": error_msg}
            else:
                return {"error": f" Unknown error fetching data for {ticker_str}: {error_msg}"}