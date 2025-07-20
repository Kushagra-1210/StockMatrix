from .logger import get_logger  # Use relative import
import sys, os
# This sys.path append is redundant because main.py already handles it. It can be removed.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.ticker_lists import fallback_tickers

logger = get_logger(__name__)


EXCHANGES = {
    "NSE": ".NS",
    "HKEX": ".HK",
    "NYSE": "",
    "LSE": ".L",
    "TSE": ".T"
}

def get_top_50_tickers(exchange):
    suffix = EXCHANGES.get(exchange)
    tickers = fallback_tickers.get(exchange, [])
    # Always return fallback tickers with suffix, no validation
    return [t + suffix if suffix and not t.endswith(suffix) else t for t in tickers]
