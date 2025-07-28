# backend/data_fetcher.py
import yfinance as yf
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor
import streamlit as st

logger = logging.getLogger(__name__)

@st.cache_data(ttl=3600) # Cache data for 1 hour in memory
def get_ticker_data(ticker_str: str):
    """
    Fetches all required financial data for a single stock in one go using parallel threads.
    The results are cached in memory for the duration of the TTL to improve performance.
    """
    try:#
        logger.info(f"Fetching all data for {ticker_str} from yfinance...")
        stock = yf.Ticker(ticker_str)
        
        # Use a thread pool to fetch all data points simultaneously for maximum speed
        with ThreadPoolExecutor(max_workers=5) as executor:
            info_future = executor.submit(lambda: stock.info)
            hist_future = executor.submit(lambda: stock.history(period="1y"))
            financials_future = executor.submit(lambda: stock.financials)
            balance_sheet_future = executor.submit(lambda: stock.balance_sheet)
            cashflow_future = executor.submit(lambda: stock.cashflow)

            # Retrieve results from the futures
            info_data = info_future.result()
            hist_data = hist_future.result()
            financials_data = financials_future.result()
            balance_sheet_data = balance_sheet_future.result()
            cashflow_data = cashflow_future.result()

            # Convert results to a serializable format (dicts) to prevent issues with caching
            # and ensure data consistency. Gracefully handle empty DataFrames.
            return {
                "info": info_data or {},
                "history": hist_data.to_dict('index') if not hist_data.empty else {},
                "financials": financials_data.to_dict() if not financials_data.empty else {},
                "balance_sheet": balance_sheet_data.to_dict() if not balance_sheet_data.empty else {},
                "cashflow": cashflow_data.to_dict() if not cashflow_data.empty else {},
            }
            
    except Exception as e: #
        logger.error(f"A critical error occurred while fetching data for {ticker_str}: {e}", exc_info=True)
        return {"error": f"Data fetching failed for {ticker_str}. The ticker might be invalid or delisted."}