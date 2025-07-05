import os
import sys

# Ensure parent directory is in the import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.market_selector import get_top_50_tickers

print("🚀 Running test for get_top_50_tickers()...\n")

def run_test():
    exchanges = ["NSE", "HKEX", "NYSE", "LSE", "TSE"]
    for exchange in exchanges:
        print(f"🔍 Testing {exchange}...")
        tickers = get_top_50_tickers(exchange)
        print(f"Top 5 tickers from {exchange}: {tickers[:5]}")
        assert isinstance(tickers, list), f"{exchange}: Output is not a list"
        assert len(tickers) > 0, f"{exchange}: No tickers returned"
        assert all(isinstance(t, str) for t in tickers), f"{exchange}: Non-string ticker found"
        print(f"✅ {exchange}: {len(tickers)} tickers validated.\n")

if __name__ == "__main__":
    run_test()
