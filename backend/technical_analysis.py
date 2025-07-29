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
    Analyzes technical indicators using a self-contained 10-factor model.
    This version is fully adaptive to the amount of historical data available.
    """
    try:
        ticker_data = get_ticker_data(ticker)
        if "error" in ticker_data:
            return ticker_data

        if not isinstance(ticker_data, dict) or "history" not in ticker_data or not ticker_data["history"]:
            return {"error": "❌ No valid historical data for TA."}

        hist = pd.DataFrame(ticker_data["history"])
        
        notes = []
        if len(hist) < 250:
            notes.append(f"Warning: Only {len(hist)} data points available. Long-term indicators may be less reliable.")

        scores = {}
        close = hist['Close']
        low = hist['Low']
        high = hist['High']
        volume = hist['Volume']

        # --- Conditionally Calculate Indicators ---

        # 1 & 2. Trend (SMA)
        if len(hist) >= 200:
            sma50 = close.rolling(window=50).mean().iloc[-1]
            sma200 = close.rolling(window=200).mean().iloc[-1]
            scores['SMA_Trend'] = 10 if sma50 > sma200 else 0
            scores['Price_vs_SMA200'] = 10 if close.iloc[-1] > sma200 else 0
        else:
            scores['SMA_Trend'] = 5
            scores['Price_vs_SMA200'] = 5
            notes.append("200-day SMA trend could not be calculated.")

        # 3. MACD
        if len(hist) >= 26:
            ema12 = _calculate_ema(close, 12)
            ema26 = _calculate_ema(close, 26)
            macd_line = ema12 - ema26
            signal_line = _calculate_ema(macd_line, 9)
            scores['MACD'] = 10 if (macd_line - signal_line).iloc[-1] > 0 else 0
        else:
            scores['MACD'] = 5
            notes.append("MACD could not be calculated.")
            
        # 4 & 5. RSI and Stochastic
        if len(hist) >= 14:
            delta = close.diff()
            gain = delta.where(delta > 0, 0).ewm(span=14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(span=14, adjust=False).mean()
            rs = gain / (loss + 1e-6)
            rsi = 100 - (100 / (1 + rs))
            scores['RSI'] = _normalize_rsi_stoch(rsi.iloc[-1])
            
            low14 = low.rolling(14).min()
            high14 = high.rolling(14).max()
            stoch_k = 100 * (close - low14) / (high14 - low14 + 1e-6)
            scores['Stoch'] = _normalize_rsi_stoch(stoch_k.iloc[-1])
        else:
            scores['RSI'] = 5
            scores['Stoch'] = 5
            notes.append("RSI and Stochastic could not be calculated.")

        # 6. Momentum
        if len(hist) >= 10:
             momentum = close.diff(10)
             last_50_days = momentum.loc[momentum.index > (momentum.index.max() - pd.Timedelta(days=50))]
             scores['Momentum'] = _normalize_momentum(last_50_days)
        else:
            scores['Momentum'] = 5
            notes.append("Momentum could not be calculated.")

        # 7. ATR (Volatility)
        if len(hist) >= 15: # ATR needs n+1 periods
            atr = _calculate_atr(high, low, close, 14).iloc[-1]
            scores['ATR_Vol'] = _normalize_volatility(atr, close.iloc[-1])
        else:
            scores['ATR_Vol'] = 5
            notes.append("ATR Volatility could not be calculated.")
            
        # 8 & 9. Volume Indicators
        if len(hist) >= 10 and 'Volume' in hist.columns and not hist['Volume'].isnull().all():
            obv = (np.sign(close.diff()) * volume).cumsum()
            scores['OBV_Trend'] = 10 if obv.diff().iloc[-1] > 0 else 0
            
            vol_ma_fast = volume.rolling(window=5).mean()
            vol_ma_slow = volume.rolling(window=10).mean()
            vo = vol_ma_fast - vol_ma_slow
            scores['Volume_Osc'] = 5 + (vo.iloc[-1] / (volume.mean() + 1e-6)) * 10
        else:
            scores['OBV_Trend'] = 5
            scores['Volume_Osc'] = 5
            notes.append("Volume indicators could not be calculated.")
        
        # 10. ADX
        if len(hist) >= 28: # ADX needs ~2N periods
            adx = _calculate_adx(high, low, close, 14)
            scores['ADX_Strength'] = 10 if adx > 25 else 0
        else:
            scores['ADX_Strength'] = 0 # Default to 0 as weak trend is the baseline
            notes.append("ADX could not be calculated.")


        if not scores:
            return {"error": "Not enough data to calculate any technical indicators."}

        final_score = np.mean(list(scores.values())) * 10
        
        if final_score >= 85: verdict = "🚀 Strong Buy"
        elif final_score >= 70: verdict = "✅ Buy"
        elif final_score >= 55: verdict = "🟢 Cautiously Optimistic"
        elif final_score >= 45: verdict = "🟡 Neutral"
        elif final_score >= 30: verdict = "🟠 Cautiously Pessimistic"
        else: verdict = "🔴 Sell"

        return {
            "ta_score": round(final_score, 2),
            "verdict": verdict,
            "period": f"Adaptive ({len(hist)} days)",
            "notes": notes,
            "indicators": {k: f"{v:.1f}/10" for k, v in scores.items()}
        }

    except Exception as e:
        logger.error(f"Failed to perform TA for {ticker}: {e}", exc_info=True)
        return {"error": f"Could not perform TA for {ticker}. Error: {e}"}
