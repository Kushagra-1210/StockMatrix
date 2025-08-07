import yfinance as yf
import pandas as pd
import logging
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import time
from backend.secondary_data_fetcher import SecondaryDataFetcher

logger = logging.getLogger(__name__)

@st.cache_data(ttl=3600)  # Cache data for 1 hour
def get_ticker_data(ticker_str: str) -> dict:
    """
    Fetch all financial and historical data for a given stock ticker using yfinance.
    Includes validation to ensure data isn't empty and logs meaningful errors.
    """
    max_retries = 5
    retry_delay = 120  # seconds

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

            # Convert data to a robust serializable format
            def to_split_dict(df):
                return df.to_dict('split') if df is not None and not df.empty else {}

            # CRITICAL: history uses 'list' for compatibility with TA module
            hist_data.reset_index(inplace=True)
            hist_dict = hist_data.to_dict('list') if not hist_data.empty else {}

            # Fetch from secondary source if needed
            fmp_fetcher = SecondaryDataFetcher()
            fmp_data = {
                "income_statement": fmp_fetcher.get_income_statement(ticker_str),
                "balance_sheet": fmp_fetcher.get_balance_sheet_statement(ticker_str),
                "cash_flow": fmp_fetcher.get_cash_flow_statement(ticker_str),
                "key_metrics": fmp_fetcher.get_key_metrics(ticker_str),
                "financial_ratios": fmp_fetcher.get_financial_ratios(ticker_str),
                "company_profile": fmp_fetcher.get_company_profile(ticker_str)
            }

            return {
                "info": info_data or {},
                "history": hist_dict,
                "financials": to_split_dict(financials_data),
                "balance_sheet": to_split_dict(balance_sheet_data),
                "cashflow": to_split_dict(cashflow_data),
                "fmp_data": fmp_data
            }

        except Exception as e:
            logger.error(f"Error fetching data for {ticker_str}: {e}")
            error_msg = str(e)
            if "No data found" in error_msg or "Invalid ticker symbol" in error_msg:
                return {"error": f" No data found for {ticker_str}. Ticker may be invalid or delisted."}
            elif "Rate limited" in error_msg or "Too Many Requests" in error_msg or "Expecting value" in error_msg:
                if attempt < max_retries - 1:
                    logger.info(f"Rate limit error. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    error_msg = "The data provider (Yahoo Finance) has rate-limited our requests. This is a temporary error. Please try again later."
                    return {"error": error_msg}
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