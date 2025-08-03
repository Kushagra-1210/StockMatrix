# backend/technical_analysis.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from backend.data_fetcher import get_ticker_data
import pandas_ta as ta
from datetime import datetime


logger = logging.getLogger(__name__)

# --- DYNAMIC EXPLANATIONS ---
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

    if indicator == "RSI": # Note: Score is inverted (lower score is more overbought/bearish)
        if score <= 25: return "Overbought: The RSI is high, suggesting the stock may be overvalued and due for a pullback. This is a bearish signal."
        if score <= 45: return "Approaching Overbought: The RSI is in the upper range, indicating potential for a reversal."
        if score < 55: return "Neutral: The RSI is in a neutral range, not indicating a strong bias."
        if score < 75: return "Approaching Oversold: The RSI is in the lower range, suggesting the stock may be undervalued."
        return "Oversold: The RSI is low, suggesting the stock may be undervalued and due for a rally. This is a bullish signal."

    if indicator == "Stoch": # Note: Score is inverted
        if score <= 25: return "Overbought: The Stochastic Oscillator is high, indicating the price is near the top of its recent range and could reverse."
        if score <= 45: return "High in Range: The price is in the upper part of its recent trading range."
        if score < 55: return "Neutral: The price is in the middle of its recent trading range."
        if score < 75: return "Low in Range: The price is in the lower part of its recent trading range."
        return "Oversold: The Stochastic Oscillator is low, indicating the price is near the bottom of its recent range and could rally."

    if indicator == "ADX_Strength":
        if score >= 75: return "Very Strong Trend: The ADX indicates a very strong trend is in place (either up or down)."
        if score >= 55: return "Strong Trend: The ADX shows a clear and strong trend."
        if score > 45: return "Developing Trend: The trend is starting to show some strength."
        return "Weak or No Trend: The market is likely ranging or the trend is very weak."

    if indicator == "ATR_Vol": # Note: Score is inverted (lower score = higher volatility)
        if score <= 25: return "High Volatility: The ATR is high relative to the price, indicating large price swings and higher risk."
        if score <= 45: return "Moderate Volatility: Price swings are noticeable."
        if score < 55: return "Average Volatility: Typical price movement for this stock."
        if score < 75: return "Low Volatility: Price swings are smaller than usual."
        return "Very Low Volatility: The ATR is low, indicating very small price swings and lower risk."

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

def industry_benchmark_zones(ticker_str: str) -> dict:
    """
    Calculate industry benchmark zones for a given stock ticker.
    """
    data = get_ticker_data(ticker_str)
    if 'error' in data:
        return data

    hist_data = pd.DataFrame(data['history'])
    info_data = data['info']

    # Check for missing values in hist_data
    if hist_data.isnull().values.any():
        logger.warning(f"Missing values detected in historical data for {ticker_str}")
        return {"error": "Missing values detected in historical data"}

    # Check for outliers in hist_data
    hist_data = hist_data[(np.abs(hist_data['Close'] - hist_data['Close'].mean()) < (3 * hist_data['Close'].std()))]
    if hist_data.empty:
        logger.warning(f"Outliers detected in historical data for {ticker_str}")
        return {"error": "Outliers detected in historical data"}

    # Calculate technical indicators
    try:
        hist_data['RSI'] = ta.rsi(hist_data['Close'], length=14)
        hist_data['Stoch'] = ta.stoch(hist_data['High'], hist_data['Low'], hist_data['Close'], length=14)
        hist_data['MACD'] = ta.macd(hist_data['Close'], fast=12, slow=26, signal=9)
        hist_data['ADX'] = ta.adx(hist_data['High'], hist_data['Low'], hist_data['Close'], length=14)
        hist_data['ATR'] = ta.atr(hist_data['High'], hist_data['Low'], hist_data['Close'], length=14)
    except Exception as e:
        logger.error(f"Error calculating technical indicators for {ticker_str}: {e}")
        return {"error": f"Error calculating technical indicators: {e}"}

    # Get industry thresholds
    industry = info_data.get('industry', 'default')
    thresholds = INDUSTRY_THRESHOLDS[industry]

    # Calculate benchmark zones
    benchmark_zones = {}
    for indicator, (lower, upper) in thresholds.items():
        benchmark_zones[indicator] = (hist_data[indicator].min(), hist_data[indicator].max())

    # Check for missing values in benchmark_zones
    if any(pd.isnull(benchmark_zones.values())):
        logger.warning(f"Missing values detected in benchmark zones for {ticker_str}")
        return {"error": "Missing values detected in benchmark zones"}

    return benchmark_zones

# --- NORMALIZATION HELPERS ---
def get_thresholds(industry: str):
    return INDUSTRY_THRESHOLDS.get(industry, INDUSTRY_THRESHOLDS['default'])

def normalize_indicator(value, neutral_low, neutral_high, bullish_is_high=True):
    if pd.isna(value): return 50.0
    if value > neutral_high:
        score = 75 + min(25, (value - neutral_high) * 2.5)
        return score if bullish_is_high else 100 - score
    elif value < neutral_low:
        score = 25 - min(25, (neutral_low - value) * 2.5)
        return score if bullish_is_high else 100 - score
    else:
        return 25 + ((value - neutral_low) / (neutral_high - neutral_low)) * 50.0

def normalize_volatility(vol_percent, low=1.5, high=7.0):
    
    if pd.isna(vol_percent): return 50.0
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
    
    hist = pd.DataFrame()
    try:
        thresholds = get_thresholds(industry)
        ticker_data = get_ticker_data(ticker)
        if "error" in ticker_data: return ticker_data
        if not isinstance(ticker_data, dict) or "history" not in ticker_data or not ticker_data["history"]:
            return {"error": "❌ No valid historical data for TA."}

        hist = pd.DataFrame(ticker_data['history'])

        # Step 1: Force daily frequency and forward-fill missing days (holidays, weekends)
        hist['Date'] = pd.to_datetime(hist['Date'])
        hist.set_index('Date', inplace=True)
        hist = hist.asfreq('B')  # Business day frequency
        hist = hist.ffill()

        # Step 2: Round OHLC prices to 2 decimals to reduce floating-point drift
        hist[['Open', 'High', 'Low', 'Close']] = hist[['Open', 'High', 'Low', 'Close']].round(2)

        # Step 3: Rename columns to lowercase (pandas_ta standard)
        hist.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)

        # --- Apply individual indicators manually for better precision
        hist['RSI_14'] = ta.rsi(hist['close'], length=14)
        macd = ta.macd(hist['close'], fast=12, slow=26, signal=9)
        hist = pd.concat([hist, macd], axis=1)
        stoch = ta.stoch(hist['high'], hist['low'], hist['close'], k=14, d=3, smooth_k=3)
        hist = pd.concat([hist, stoch], axis=1)
        hist['ADX_14'] = ta.adx(hist['high'], hist['low'], hist['close'], length=14)['ADX_14']
        hist['ATR_14'] = ta.atr(hist['high'], hist['low'], hist['close'], length=14)
        hist['OBV'] = ta.obv(hist['close'], hist['volume'])
        hist['SMA_50'] = ta.sma(hist['close'], length=50)
        hist['SMA_200'] = ta.sma(hist['close'], length=200)

        notes, scores, explanations = [], {}, {}

        # --- SMA Trend ---
        price = safe_latest_value(hist, 'close')
        sma50 = safe_latest_value(hist, 'SMA_50')
        sma200 = safe_latest_value(hist, 'SMA_200')

        if price is not None and sma50 is not None and sma200 is not None:
            if price > sma50 > sma200:
                scores['SMA_Trend'] = 100.0
            elif sma50 > price > sma200:
                scores['SMA_Trend'] = 70.0
            elif sma50 > sma200:
                scores['SMA_Trend'] = 60.0
            elif price < sma50 < sma200:
                scores['SMA_Trend'] = 0.0
            elif sma50 < price < sma200:
                scores['SMA_Trend'] = 30.0
            else:
                scores['SMA_Trend'] = 50.0
        else:
            scores['SMA_Trend'] = 50.0
            notes.append("SMA trend could not be calculated.")
        explanations['SMA_Trend'] = get_dynamic_explanation('SMA_Trend', scores['SMA_Trend'])

        # --- MACD ---
        macd_val = safe_latest_value(hist, 'MACDh_12_26_9')
        if macd_val is not None:
            low, high = thresholds['MACD']
            scores['MACD'] = normalize_indicator(macd_val, low, high, bullish_is_high=True)
        else:
            scores['MACD'] = 50.0
            notes.append("MACD could not be calculated (NaN or missing).")
        explanations['MACD'] = get_dynamic_explanation('MACD', scores['MACD'])

        # --- RSI & Stochastic ---
        rsi = safe_latest_value(hist, 'RSI_14')
        if rsi is not None:
            low, high = thresholds['RSI']
            scores['RSI'] = normalize_indicator(rsi, low, high, bullish_is_high=False)
        else:
            scores['RSI'] = 50.0
            notes.append("RSI could not be calculated (NaN or missing).")
        explanations['RSI'] = get_dynamic_explanation('RSI', scores['RSI'])

        stoch = safe_latest_value(hist, 'STOCHk_14_3_3')
        if stoch is not None:
            low, high = thresholds['Stoch']
            scores['Stoch'] = normalize_indicator(stoch, low, high, bullish_is_high=False)
        else:
            scores['Stoch'] = 50.0
            notes.append("Stochastic could not be calculated.")
        explanations['Stoch'] = get_dynamic_explanation('Stoch', scores['Stoch'])

        # --- ADX ---
        adx = safe_latest_value(hist, 'ADX_14')
        if adx is not None:
            low, high = thresholds['ADX']
            scores['ADX_Strength'] = normalize_indicator(adx, low, high, bullish_is_high=True)
        else:
            scores['ADX_Strength'] = 50.0
            notes.append("ADX could not be calculated.")
        explanations['ADX_Strength'] = get_dynamic_explanation('ADX_Strength', scores['ADX_Strength'])

        # --- ATR ---
        atr_val = safe_latest_value(hist, 'ATR_14')
        close_price = safe_latest_value(hist, 'close')
        if atr_val is not None and close_price is not None and close_price != 0:
            atr_percent = (atr_val / close_price) * 100
            low, high = thresholds['ATR']
            scores['ATR_Vol'] = normalize_volatility(atr_percent, low, high)
        else:
            scores['ATR_Vol'] = 50.0
            notes.append("ATR Volatility could not be calculated.")
        explanations['ATR_Vol'] = get_dynamic_explanation('ATR_Vol', scores['ATR_Vol'])

        # --- OBV ---
        if 'OBV' in hist.columns:
            obv_series = hist['OBV'].dropna().tail(10)
            if len(obv_series) > 1 and obv_series.iloc[-1] != obv_series.iloc[0]:
                scores['OBV_Trend'] = 100.0 if obv_series.iloc[-1] > obv_series.iloc[0] else 0.0
            else:
                scores['OBV_Trend'] = 50.0
        else:
            scores['OBV_Trend'] = 50.0
            notes.append("OBV trend could not be calculated.")
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