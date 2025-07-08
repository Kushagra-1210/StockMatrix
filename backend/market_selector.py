from backend.logger import get_logger
import yfinance as yf
from config.ticker_lists import fallback_tickers

logger = get_logger(__name__)

EXCHANGES = {
    "NSE": ".NS",
    "HKEX": ".HK",
    "NYSE": "",
    "LSE": ".L",
    "TSE": ".T"
}

def validate_ticker(ticker):
    try:
        info = yf.Ticker(ticker).info
        return 'shortName' in info
    except Exception as e:
        logger.warning(f"Validation failed for {ticker}: {e}")
        return False

def get_top_50_tickers(exchange):
    suffix = EXCHANGES.get(exchange)
    tickers = fallback_tickers.get(exchange, [])

    valid = []
    for t in tickers:
        full_ticker = t + suffix if suffix and not t.endswith(suffix) else t
        if validate_ticker(full_ticker):
            valid.append(full_ticker)
        if len(valid) >= 50:
            break

    logger.info(f"{len(valid)} valid tickers for {exchange}")
    return valid
