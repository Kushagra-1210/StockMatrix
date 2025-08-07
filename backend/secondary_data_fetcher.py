import requests
import os

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

if __name__ == '__main__':
    # Example Usage (replace with your actual API key or set as environment variable)
    # You can get a free API key from https://financialmodelingprep.com/developer/docs/
    # os.environ["FMP_API_KEY"] = "YOUR_FMP_API_KEY" 
    
    fetcher = SecondaryDataFetcher()
    if fetcher.api_key:
        print("Fetching Apple Inc. (AAPL) income statement:")
        income_statement = fetcher.get_income_statement("AAPL")
        if income_statement:
            print(income_statement[0] if income_statement else "No data")

        print("\nFetching Apple Inc. (AAPL) key metrics:")
        key_metrics = fetcher.get_key_metrics("AAPL")
        if key_metrics:
            print(key_metrics[0] if key_metrics else "No data")
    else:
        print("FMP_API_KEY environment variable not set. Please set it to run the example.")
