# backend/technical_analysis.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from backend.data_provider import DataProvider # Using the new DataProvider
import pandas_ta as ta
from datetime import datetime

logger = logging.getLogger(__name__)

# --- DYNAMIC EXPLANATIONS (Updated for new logic) ---
def get_dynamic_explanation(indicator: str, score: float, **kwargs) -> str:
    """Generates a dynamic explanation based on the indicator and its score."""
    if indicator == "SMA_Trend":
        if score >= 95: return "Strong Uptrend: Price is well above both the 50-day and 200-day moving averages, indicating strong bullish momentum."
        if score >= 65: return "Uptrend: Price is above its moving averages, suggesting positive market sentiment."
        if score >= 45: return "Neutral Trend: Price is hovering around its moving averages, indicating a lack of a clear trend."
        if score >= 25: return "Downtrend: Price is below its moving averages, suggesting negative market sentiment."
        return "Strong Downtrend: Price is well below both moving averages, indicating strong bearish momentum."

    if indicator == "MACD":
        if score >= 75: return "Strong Bullish Momentum: The MACD line is significantly above the signal line, indicating strong buying pressure."
        if score >= 55: return "Bullish Momentum: The MACD is positive, suggesting upward price momentum."
        if score > 45: return "Neutral: The MACD is near the signal line, indicating a balance between buyers and sellers."
        if score > 25: return "Bearish Momentum: The MACD is negative, suggesting downward price momentum."
        return "Strong Bearish Momentum: The MACD line is significantly below the signal line, indicating strong selling pressure."

    if indicator == "RSI":
        raw_rsi = kwargs.get('value', 50)
        if raw_rsi > 70: return f"Overbought ({raw_rsi:.1f}): The RSI is in overbought territory, suggesting the stock may be overvalued and due for a pullback. This is a bearish sign, hence the lower score."
        if raw_rsi < 30: return f"Oversold ({raw_rsi:.1f}): The RSI is low, suggesting the stock may be undervalued and due for a rally. This is a bullish reversal signal."
        return f"Neutral ({raw_rsi:.1f}): The RSI is in a neutral range, not indicating a strong directional bias."

    if indicator == "Stoch":
        raw_stoch = kwargs.get('value', 50)
        if raw_stoch > 80: return f"Overbought ({raw_stoch:.1f}): The Stochastic is high, indicating the price is near the top of its recent range and could reverse. This is a bearish sign."
        if raw_stoch < 20: return f"Oversold ({raw_stoch:.1f}): The Stochastic is low, indicating the price is near the bottom of its recent range and could rally. This is a bullish reversal signal."
        return f"Neutral ({raw_stoch:.1f}): The price is in the middle of its recent trading range."

    if indicator == "ADX_Strength":
        if score >= 75: return "Very Strong Trend: The ADX indicates a very strong trend is in place (either up or down)."
        if score >= 55: return "Strong Trend: The ADX shows a clear and strong trend."
        return "Weak or No Trend: The market is likely ranging or the trend is very weak."

    if indicator == "ATR_Vol":
        if score <= 30: return "High Volatility: The ATR is high relative to the price, indicating large price swings and higher risk."
        if score <= 60: return "Moderate Volatility: Price swings are noticeable."
        return "Low Volatility: The ATR is low, indicating very small price swings and lower risk."

    if indicator == "OBV_Trend":
        if score >= 95: return "Strong Buying Pressure: On-Balance Volume is in a strong uptrend, suggesting accumulation."
        if score <= 5: return "Strong Selling Pressure: On-Balance Volume is in a strong downtrend, suggesting distribution."
        return "Neutral Volume: Volume flow does not indicate a strong buying or selling trend."

    return "No specific explanation available for this score."


# --- INDUSTRY BENCHMARK ZONES ---
INDUSTRY_THRESHOLDS = {
    'default': {'RSI': (40, 60), 'Stoch': (40, 60), 'MACD': (-0.15, 0.15), 'ADX': (20, 25), 'ATR': (1.5, 7.0)},
    'Energy': {'RSI': (35, 65), 'Stoch': (35, 65), 'MACD': (-0.25, 0.25), 'ADX': (18, 28), 'ATR': (2.0, 8.0)},
    'FMCG': {'RSI': (45, 55), 'Stoch': (45, 55), 'MACD': (-0.1, 0.1), 'ADX': (15, 22), 'ATR': (1.0, 4.0)},
    'Banking': {'RSI': (38, 62), 'Stoch': (38, 62), 'MACD': (-0.2, 0.2), 'ADX': (22, 30), 'ATR': (1.8, 6.0)}
}

# --- NORMALIZATION HELPERS (Updated Logic) ---
def get_thresholds(industry: str):
    return INDUSTRY_THRESHOLDS.get(industry, INDUSTRY_THRESHOLDS['default'])

def normalize_momentum(value, neutral_low, neutral_high):
    """Normalizes momentum indicators like MACD where higher is more bullish."""
    if pd.isna(value): return 50.0
    if value > neutral_high:
        score = 75 + min(25, (value - neutral_high) * 5) # More sensitive scaling
    elif value < neutral_low:
        score = 25 - min(25, (neutral_low - value) * 5)
    else:
        # Scale score between 25 and 75 in the neutral zone
        score = 25 + ((value - neutral_low) / (neutral_high - neutral_low)) * 50.0
    return max(0.0, min(100.0, score))

def normalize_oscillator(value, oversold=30, overbought=70):
    """
    Normalizes oscillators like RSI and Stochastics.
    Treats oversold as bullish (high score) and overbought as bearish (low score).
    """
    if pd.isna(value): return 50.0
    
    if value < oversold:
        # Strong bullish signal as it's oversold
        return 75 + min(25, (oversold - value) * 1.5)
    elif value > overbought:
        # Strong bearish signal as it's overbought
        return 25 - min(25, (value - overbought) * 1.5)
    else:
        # Neutral zone, scales linearly between 25 and 75
        return 25 + ((value - oversold) / (overbought - oversold)) * 50.0

def normalize_volatility(vol_percent, low=1.5, high=7.0):
    if pd.isna(vol_percent): return 50.0
    # Lower volatility gets a higher score
    score = 100 - ((vol_percent - low) / (high - low)) * 100
    return max(0.0, min(100.0, score))

def safe_latest_value(df, column_name):
    """Get last non-NaN value from a column, or return None."""
    if column_name in df.columns:
        series = df[column_name].dropna()
        if not series.empty:
            return series.iloc[-1]
    return None

# --- MAIN ANALYSIS FUNCTION ---
def analyze_technical_indicators(ticker: str, industry: str = 'default', basis: str = "annual") -> dict:
    try:
        provider = DataProvider(ticker)
        thresholds = get_thresholds(industry)
        hist = provider.get_history()

        if hist.empty:
            return {"error": "❌ No valid historical data for TA."}

        # --- Data Preparation (CORRECTED) ---
        # We will work directly with the provided trading data without resampling.
        hist['Date'] = pd.to_datetime(hist['Date'])
        hist.set_index('Date', inplace=True)
        hist.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        hist[['open', 'high', 'low', 'close']] = hist[['open', 'high', 'low', 'close']].round(2)

        # --- Indicator Calculations ---
        # The pandas-ta library correctly handles non-continuous dates (weekends/holidays)
        hist.ta.rsi(length=14, append=True)
        hist.ta.macd(fast=12, slow=26, signal=9, append=True)
        hist.ta.stoch(k=14, d=3, smooth_k=3, append=True)
        hist.ta.adx(length=14, append=True)
        hist.ta.atr(length=14, append=True)
        hist.ta.obv(append=True)
        hist.ta.sma(length=50, append=True)
        hist.ta.sma(length=200, append=True)

        notes, scores, explanations = [], {}, {}
        
        # --- Scoring Logic ---
        price = safe_latest_value(hist, 'close')
        sma50 = safe_latest_value(hist, 'SMA_50')
        sma200 = safe_latest_value(hist, 'SMA_200')

        if all(v is not None for v in [price, sma50, sma200]):
            if price > sma50 > sma200: scores['SMA_Trend'] = 100.0
            elif price > sma50 and price > sma200: scores['SMA_Trend'] = 70.0
            elif price < sma50 < sma200: scores['SMA_Trend'] = 0.0
            elif price < sma50 and price < sma200: scores['SMA_Trend'] = 30.0
            else: scores['SMA_Trend'] = 50.0
        else:
            scores['SMA_Trend'] = 50.0
            notes.append("SMA trend could not be calculated.")
        explanations['SMA_Trend'] = get_dynamic_explanation('SMA_Trend', scores['SMA_Trend'])

        macd_val = safe_latest_value(hist, 'MACDh_12_26_9')
        scores['MACD'] = normalize_momentum(macd_val, thresholds['MACD'][0], thresholds['MACD'][1])
        explanations['MACD'] = get_dynamic_explanation('MACD', scores['MACD'], value=macd_val)

        rsi_val = safe_latest_value(hist, 'RSI_14')
        scores['RSI'] = normalize_oscillator(rsi_val, 30, 70)
        explanations['RSI'] = get_dynamic_explanation('RSI', scores['RSI'], value=rsi_val)

        stoch_val = safe_latest_value(hist, 'STOCHk_14_3_3')
        scores['Stoch'] = normalize_oscillator(stoch_val, 20, 80)
        explanations['Stoch'] = get_dynamic_explanation('Stoch', scores['Stoch'], value=stoch_val)
        
        adx_val = safe_latest_value(hist, 'ADX_14')
        scores['ADX_Strength'] = normalize_momentum(adx_val, thresholds['ADX'][0], thresholds['ADX'][1])
        explanations['ADX_Strength'] = get_dynamic_explanation('ADX_Strength', scores['ADX_Strength'], value=adx_val)

        atr_val = safe_latest_value(hist, 'ATRr_14')
        if atr_val is not None:
            scores['ATR_Vol'] = normalize_volatility(atr_val, thresholds['ATR'][0], thresholds['ATR'][1])
        else:
            scores['ATR_Vol'] = 50.0
            notes.append("ATR Volatility could not be calculated.")
        explanations['ATR_Vol'] = get_dynamic_explanation('ATR_Vol', scores['ATR_Vol'], value=atr_val)

        obv_series = hist['OBV'].dropna().tail(10)
        if len(obv_series) > 1:
            scores['OBV_Trend'] = 100.0 if obv_series.iloc[-1] > obv_series.iloc[0] else 0.0
        else:
            scores['OBV_Trend'] = 50.0
        explanations['OBV_Trend'] = get_dynamic_explanation('OBV_Trend', scores['OBV_Trend'])

        # --- Final Score & Verdict ---
        final_score = np.mean(list(scores.values()))
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
            "indicators": {k: f"{v:.1f}/100" for k, v in scores.items()},
            "explanations": explanations
        }

    except Exception as e:
        logger.error(f"Failed to perform TA for {ticker}: {e}", exc_info=True)
        return {"error": f"Could not perform TA. Error: {e}"}
