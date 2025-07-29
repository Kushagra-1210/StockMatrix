# backend/technical_analysis.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from backend.data_fetcher import get_ticker_data

logger = logging.getLogger(__name__)

# --- 1. RE-ENGINEERED NORMALIZATION HELPERS ---

def normalize_indicator(value, neutral_low, neutral_high, bullish_is_high=True):
    """
    A universal function to normalize any indicator to a 0-10 scale.
    - value: The indicator's real value (e.g., RSI of 60).
    - neutral_low, neutral_high: The range considered neutral (e.g., RSI 40-60).
    - bullish_is_high: True if a higher value is bullish (like MACD), False if a lower value is bullish (like RSI oversold).
    """
    if pd.isna(value): return 5.0

    # Bullish zone
    if value > neutral_high:
        score = 7.5 + min(2.5, (value - neutral_high) * 0.2) # Scales from 7.5 to 10
        return score if bullish_is_high else 10 - score
    # Bearish zone
    elif value < neutral_low:
        score = 2.5 - min(2.5, (neutral_low - value) * 0.2) # Scales from 2.5 to 0
        return score if bullish_is_high else 10 - score
    # Neutral zone
    else:
        # Linearly scale between 2.5 and 7.5 within the neutral zone
        return 2.5 + (value - neutral_low) / (neutral_high - neutral_low) * 5.0

def normalize_volatility(vol_percent):
    """
    Normalizes volatility. Lower volatility is better (higher score).
    A volatility of 1.5% is considered ideal (score 10).
    A volatility of 7% or more is considered high risk (score 0).
    """
    if pd.isna(vol_percent): return 5.0
    # Create a reverse linear scale
    score = 10 - ((vol_percent - 1.5) / (7.0 - 1.5)) * 10
    return max(0.0, min(10.0, score))


# --- 2. SELF-CONTAINED INDICATOR CALCULATORS (No changes needed here) ---
def _calculate_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def _calculate_atr(high, low, close, length=14):
    tr1 = abs(high - low); tr2 = abs(high - close.shift()); tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return _calculate_ema(tr, span=length)

def _calculate_adx(high, low, close, length=14):
    dm_plus = high.diff(); dm_minus = low.diff()
    dm_plus[(dm_plus < 0) | (dm_plus <= -dm_minus)] = 0.0
    dm_minus[(dm_minus < 0) | (dm_minus <= dm_plus)] = 0.0
    tr = _calculate_atr(high, low, close, length)
    tr[tr == 0] = 1e-6
    adx_plus = 100 * _calculate_ema(dm_plus, length) / tr
    adx_minus = 100 * _calculate_ema(dm_minus, length) / tr
    adx_sum = adx_plus + adx_minus
    adx_sum[adx_sum == 0] = 1e-6
    adx = 100 * abs(adx_plus - adx_minus) / adx_sum
    return _calculate_ema(adx, length).iloc[-1]


# --- 3. MAIN ANALYSIS FUNCTION WITH IMPROVED LOGIC ---
def analyze_technical_indicators(ticker: str, basis: str = "annual") -> dict:
    """
    Analyzes technical indicators with improved, more logical scoring.
    """
    try:
        ticker_data = get_ticker_data(ticker)
        if "error" in ticker_data: return ticker_data

        if not isinstance(ticker_data, dict) or "history" not in ticker_data or not ticker_data["history"]:
            return {"error": "❌ No valid historical data for TA."}

        hist = pd.DataFrame(ticker_data["history"])
        hist['Date'] = pd.to_datetime(hist['Date'])
        hist.set_index('Date', inplace=True)
        
        notes, scores = [], {}
        close = hist['Close']; low = hist['Low']; high = hist['High']; volume = hist['Volume']

        # --- Nuanced SMA Trend Scoring ---
        if len(hist) >= 200:
            price = close.iloc[-1]
            sma50 = close.rolling(window=50).mean().iloc[-1]
            sma200 = close.rolling(window=200).mean().iloc[-1]
            if price > sma50 > sma200: scores['SMA_Trend'] = 10.0 # Strong uptrend
            elif sma50 > price > sma200: scores['SMA_Trend'] = 7.0  # Pullback in uptrend
            elif sma50 > sma200: scores['SMA_Trend'] = 6.0          # Generally bullish context
            elif price < sma50 < sma200: scores['SMA_Trend'] = 0.0  # Strong downtrend
            elif sma50 < price < sma200: scores['SMA_Trend'] = 3.0  # Rally in downtrend
            else: scores['SMA_Trend'] = 5.0                         # Mixed signals
        else:
            scores['SMA_Trend'] = 5.0
            notes.append("200-day SMA trend could not be calculated.")

        # --- MACD Scoring ---
        if len(hist) >= 26:
            ema12 = _calculate_ema(close, 12); ema26 = _calculate_ema(close, 26)
            macd_line = ema12 - ema26; signal_line = _calculate_ema(macd_line, 9)
            macd_hist = (macd_line - signal_line).iloc[-1]
            # A positive and rising histogram is most bullish.
            scores['MACD'] = normalize_indicator(macd_hist, -0.1, 0.1, bullish_is_high=True)
        else:
            scores['MACD'] = 5.0; notes.append("MACD could not be calculated.")

        # --- RSI & Stochastic Scoring ---
        if len(hist) >= 14:
            delta = close.diff()
            gain = delta.where(delta > 0, 0).ewm(span=14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(span=14, adjust=False).mean()
            rsi = 100 - (100 / (1 + (gain / (loss + 1e-6))))
            # RSI is a reversal indicator: low values (oversold) are bullish.
            scores['RSI'] = normalize_indicator(rsi.iloc[-1], 40, 60, bullish_is_high=False)
            
            low14 = low.rolling(14).min(); high14 = high.rolling(14).max()
            stoch_k = 100 * (close - low14) / (high14 - low14 + 1e-6)
            # Stochastic is also a reversal indicator.
            scores['Stoch'] = normalize_indicator(stoch_k.iloc[-1], 40, 60, bullish_is_high=False)
        else:
            scores['RSI'] = 5.0; scores['Stoch'] = 5.0
            notes.append("RSI and Stochastic could not be calculated.")

        # --- ADX Trend Strength Scoring ---
        if len(hist) >= 28:
            adx = _calculate_adx(high, low, close, 14)
            # High ADX means strong trend (either up or down), which is good for analysis.
            scores['ADX_Strength'] = normalize_indicator(adx, 20, 25, bullish_is_high=True)
        else:
            scores['ADX_Strength'] = 5.0; notes.append("ADX could not be calculated.")

        # --- ATR Volatility Scoring ---
        if len(hist) >= 15:
            atr = _calculate_atr(high, low, close, 14).iloc[-1]
            atr_percent = (atr / close.iloc[-1]) * 100
            scores['ATR_Vol'] = normalize_volatility(atr_percent)
        else:
            scores['ATR_Vol'] = 5.0; notes.append("ATR Volatility could not be calculated.")

        # --- Volume Scoring ---
        if len(hist) >= 10 and 'Volume' in hist.columns:
            obv = (np.sign(close.diff()) * volume).cumsum()
            # Rising OBV is bullish
            scores['OBV_Trend'] = 10.0 if obv.iloc[-1] > obv.iloc[-5] else 0.0
        else:
            scores['OBV_Trend'] = 5.0; notes.append("OBV could not be calculated.")

        # --- Final Score & Verdict ---
        final_score = np.mean(list(scores.values())) * 10
        
        if final_score >= 80: verdict = "🚀 Strong Buy"
        elif final_score >= 65: verdict = "✅ Buy"
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
        return {"error": f"Could not perform TA. Error: {e}"} 