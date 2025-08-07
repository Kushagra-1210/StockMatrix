import requests
import os
import random
import sys

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.ticker_lists import fallback_tickers

class SecondaryDataFetcher:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        self.base_url = "https://financialmodelingprep.com/api/v3"

    def _make_request(self, endpoint, params=None):
        if not self.api_key:
            print("FMP API key not set. Cannot fetch secondary data.")
            return None

        url = f"{self.base_url}/{endpoint}"
        all_params = {"apikey": self.api_key}
        if params:
            all_params.update(params)

        try:
            response = requests.get(url, params=all_params)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from FMP: {e}")
            return None

    def get_income_statement(self, ticker, period='annual', limit=1):
        """Fetches income statement data."""
        endpoint = f"income-statement/{ticker}"
        params = {"period": period, "limit": limit}
        return self._make_request(endpoint, params)

    def get_balance_sheet_statement(self, ticker, period='annual', limit=1):
        """Fetches balance sheet data."""
        endpoint = f"balance-sheet-statement/{ticker}"
        params = {"period": period, "limit": limit}
        return self._make_request(endpoint, params)

    def get_cash_flow_statement(self, ticker, period='annual', limit=1):
        """Fetches cash flow statement data."""
        endpoint = f"cash-flow-statement/{ticker}"
        params = {"period": period, "limit": limit}
        return self._make_request(endpoint, params)

    def get_key_metrics(self, ticker, period='annual', limit=1):
        """Fetches key metrics data."""
        endpoint = f"key-metrics/{ticker}"
        params = {"period": period, "limit": limit}
        return self._make_request(endpoint, params)

    def get_financial_ratios(self, ticker, period='annual', limit=1):
        """Fetches financial ratios data."""
        endpoint = f"ratios/{ticker}"
        params = {"period": period, "limit": limit}
        return self._make_request(endpoint, params)

    def get_company_profile(self, ticker):
        """Fetches company profile data."""
        endpoint = f"profile/{ticker}"
        return self._make_request(endpoint)

    def get_historical_price_data(self, ticker):
        """Fetches historical price data."""
        endpoint = f"historical-price-full/{ticker}"
        return self._make_request(endpoint)

if __name__ == '__main__':
    # This block is for testing the FMP API key.
    # It will pick a random stock from your ticker lists and try to fetch its data.
    # To run this test, execute `python backend/secondary_data_fetcher.py` in your terminal.
    
    fetcher = SecondaryDataFetcher()
    if fetcher.api_key:
        # Flatten the dictionary of tickers into a single list
        all_tickers = [ticker for market_tickers in fallback_tickers.values() for ticker in market_tickers]
        if not all_tickers:
            print("No tickers found in the ticker lists.")
        else:
            random_ticker = random.choice(all_tickers)
            print(f"Testing FMP API key with a random stock: {random_ticker}")
            profile = fetcher.get_company_profile(random_ticker)
            if profile:
                print("Successfully fetched data:")
                print(profile[0] if profile else "No data")
            else:
                print("Failed to fetch data. Please check your FMP_API_KEY.")
    else:
        print("FMP_API_KEY environment variable not set. Please set it to run the test.")
