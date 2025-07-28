# backend/technical_analysis.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


# --- Helper functions to normalize indicator values to a 0-10 scale ---
def _normalize_rsi_stoch(value):
    """Normalizes RSI/Stochastic. Lower values (oversold) get a higher score."""
    if pd.isna(value): return 5 # Neutral score for no data
    if value < 30:
        return 7 + (30 - value) / 10  # Score between 7 and 10
    if value > 70:
        return 3 - (value - 70) / 10  # Score between 0 and 3
    # Neutral zone
    return 3 + (70 - value) / 10 * 0.1 # Score between 3 and 7

def _normalize_momentum(series):
    """Normalizes a momentum series to a 0-10 scale based on its recent range."""
    if series.empty or len(series) < 2: return 5
    # Scale momentum values from the last 50 days to a 0-10 range
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val: return 5 # Avoid division by zero
    scaled_value = 10 * (series.iloc[-1] - min_val) / (max_val - min_val)
    return max(0, min(10, scaled_value))

def _normalize_volatility(value, price):
    """Normalizes volatility indicators. Lower volatility gets a higher score."""
    if pd.isna(value) or price == 0: return 5
    # Express volatility as a percentage of the price
    vol_pct = (value / price) * 100
    # A 5% volatility is considered high, gets a low score.
    score = 10 - (vol_pct * 2)
    return max(0, min(10, score))

# --- Self-Contained Indicator Calculation Functions ---
def _calculate_ema(series, span):
    """Calculates Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()

def _calculate_atr(high, low, close, length=14):
    """Calculates Average True Range."""
    tr1 = abs(high - low)
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return _calculate_ema(tr, span=length)

def _calculate_adx(high, low, close, length=14):
    """Calculates the Average Directional Index (ADX)."""
    dm_plus = high.diff()
    dm_minus = low.diff()
    dm_plus[(dm_plus < 0) | (dm_plus <= -dm_minus)] = 0.0
    dm_minus[(dm_minus < 0) | (dm_minus <= dm_plus)] = 0.0
    
    tr = _calculate_atr(high, low, close, length)
    tr[tr == 0] = 0.0001 # Avoid division by zero
    
    adx_plus = 100 * _calculate_ema(dm_plus, length) / tr
    adx_minus = 100 * _calculate_ema(dm_minus, length) / tr
    
    adx_sum = adx_plus + adx_minus
    adx_sum[adx_sum == 0] = 0.0001 # Avoid division by zero
    
    adx = 100 * abs(adx_plus - adx_minus) / adx_sum
    return _calculate_ema(adx, length).iloc[-1]

# --- Main Analysis Function ---
from backend.data_fetcher import get_ticker_data

def analyze_technical_indicators(ticker: str, basis: str = "annual") -> dict:
    """
    Analyzes technical indicators using a self-contained 10-factor model, using centralized data fetcher.
    """
    try:
        # Use centralized fetcher for price history
        ticker_data = get_ticker_data(ticker)
        logger.debug(f"Ticker data fetched for {ticker}: {type(ticker_data)}")

        if not isinstance(ticker_data, dict):
            return {"error": f"Invalid data returned for {ticker}: {ticker_data}"}
        if "error" in ticker_data:
            return ticker_data
        
        hist_dict = ticker_data.get("history", {})
        if not isinstance(hist_dict, dict) or "Close" not in hist_dict:
            return {"error": f"No valid historical data for TA for {ticker}."}

        hist = pd.DataFrame(hist_dict)
        # Use last 250 rows for TA (ensure enough for 200-day SMA)
        if len(hist) < 200:
            return {"error": "Not enough historical data for TA."}
        hist = hist.tail(250)

        # --- Define local variables for convenience ---
        close = hist['Close']
        low = hist['Low']
        high = hist['High']
        volume = hist['Volume']
        
        # --- Calculate all indicators manually ---
        # 1. Trend
        sma50 = close.rolling(window=50).mean().iloc[-1]
        sma200 = close.rolling(window=200).mean().iloc[-1]
        
        # 2. MACD
        ema12 = _calculate_ema(close, 12)
        ema26 = _calculate_ema(close, 26)
        macd_line = ema12 - ema26
        signal_line = _calculate_ema(macd_line, 9)
        macd_hist = macd_line - signal_line

        # 3. RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(span=14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=14, adjust=False).mean()
        loss[loss == 0] = 0.0001 # Avoid division by zero
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # 4. Stochastic Oscillator
        low14 = low.rolling(14).min()
        high14 = high.rolling(14).max()
        stoch_k = 100 * (close - low14) / (high14 - low14)
        
        # 5. Momentum
        momentum = close.diff(10)

        # 6. ATR (for volatility scoring)
        atr = _calculate_atr(high, low, close, 14).iloc[-1]

        # 7. Bollinger Band Width
        sma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        bbw_raw = (4 * std20 / sma20)
        bbw = bbw_raw.iloc[-1] * 100 # Express as a percentage

        # 8. OBV
        obv = (np.sign(close.diff()) * volume).cumsum()
        
        # 9. Volume Oscillator
        vol_ma_fast = volume.rolling(window=5).mean()
        vol_ma_slow = volume.rolling(window=10).mean()
        vo = vol_ma_fast - vol_ma_slow

        # 10. ADX
        adx = _calculate_adx(high, low, close, 14)

        # --- Scoring (0-10 for each) ---
        scores = {}
        scores['SMA'] = 10 if sma50 > sma200 else 0
        scores['MACD'] = 10 if macd_hist.iloc[-1] > 0 else 0
        scores['RSI'] = _normalize_rsi_stoch(rsi.iloc[-1])
        scores['Stoch'] = _normalize_rsi_stoch(stoch_k.iloc[-1])
        scores['SMA200'] = 10 if close.iloc[-1] > sma200 else 0
        last_50 = momentum.loc[momentum.index > (momentum.index.max() - pd.Timedelta(days=50))]
        scores['Momentum'] = _normalize_momentum(last_50)

        scores['ATR'] = _normalize_volatility(atr, close.iloc[-1])
        scores['BBW'] = 10 - max(0, min(10, bbw)) # Lower width = higher score
        scores['OBV'] = 10 if obv.diff().iloc[-1] > 0 else 0
        scores['VolumeOsc'] = 5 + (vo.iloc[-1] / volume.mean()) * 10 if not pd.isna(vo.iloc[-1]) else 5
        scores['ADX'] = 10 if adx > 25 else 0

        # --- Final Score & Signal ---
        final_score = np.mean(list(scores.values())) * 10
        
        if final_score >= 90:
            verdict = "🚀 Strong Buy: Extremely bullish technicals across all indicators."
        elif final_score >= 80:
            verdict = "✅ Buy: Most technicals are positive."
        elif final_score >= 65:
            verdict = "🟢 Bullish: Uptrend with strong signals."
        elif final_score >= 45:
            verdict = "🟡 Neutral: Mixed or sideways signals."
        elif final_score >= 25:
            verdict = "🟠 Cautious: Weak or deteriorating technicals."
        else:
            verdict = "🔴 Bearish: Strong downtrend or negative signals."

        return {
            "ta_score": round(final_score, 2),
            "verdict": verdict,
            "period": "200-Day",
            "ta_breakdown": {k: f"{v:.1f}/10" for k, v in scores.items()}
        }
    except Exception as e:
        logger.error(f"Failed to perform TA for {ticker}: {e}", exc_info=True)
        return {"error": f"Could not perform TA for {ticker}. Error: {e}"}