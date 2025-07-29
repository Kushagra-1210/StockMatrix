# backend/data_fetcher.py

import yfinance as yf
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor
import streamlit as st

logger = logging.getLogger(__name__)

@st.cache_data(ttl=3600)  # Cache data for 1 hour
def get_ticker_data(ticker_str: str) -> dict:
    """
    Fetch all financial and historical data for a given stock ticker using yfinance.
    Includes validation to ensure data isn't empty and logs meaningful errors.
    """
    try:
        logger.info(f"Fetching all data for {ticker_str} from yfinance...")
        stock = yf.Ticker(ticker_str)

        with ThreadPoolExecutor(max_workers=5) as executor:
            info_future = executor.submit(lambda: stock.info)
            hist_future = executor.submit(lambda: stock.history(period="max"))
            financials_future = executor.submit(lambda: stock.financials)
            balance_sheet_future = executor.submit(lambda: stock.balance_sheet)
            cashflow_future = executor.submit(lambda: stock.cashflow)

            # Get data from futures
            info_data = info_future.result()
            hist_data = hist_future.result()
            financials_data = financials_future.result()
            balance_sheet_data = balance_sheet_future.result()
            cashflow_data = cashflow_future.result()

        # Validate data availability
        if hist_data is None or hist_data.empty:
            return {"error": f"❌ No historical price data found for {ticker_str}. Ticker may be invalid or delisted."}

        if not info_data:
            return {"error": f"❌ No company info found for {ticker_str}. Ticker may be invalid or restricted."}

        # Convert data to serializable format
        return {
            "info": info_data or {},
            "history": hist_data.to_dict('index') if not hist_data.empty else {},
            "financials": financials_data.to_dict() if not financials_data.empty else {},
            "balance_sheet": balance_sheet_data.to_dict() if not balance_sheet_data.empty else {},
            "cashflow": cashflow_data.to_dict() if not cashflow_data.empty else {},
        }

    except Exception as e:
        logger.error(f"Error fetching data for {ticker_str}: {e}", exc_info=True)
        return {"error": f"❌ Data fetching failed for {ticker_str}. Exception: {str(e)}"}
