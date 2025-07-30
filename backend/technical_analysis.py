# backend/technical_analysis.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from backend.data_fetcher import get_ticker_data
import pandas_ta as ta
from datetime import datetime


logger = logging.getLogger(__name__)

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
    try:
        thresholds = get_thresholds(industry)
        ticker_data = get_ticker_data(ticker)
        if "error" in ticker_data: return ticker_data
        if not isinstance(ticker_data, dict) or "history" not in ticker_data or not ticker_data["history"]:
            return {"error": "❌ No valid historical data for TA."}

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

        notes, scores = [], {}

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


        # --- MACD ---
        macd_val = safe_latest_value(hist, 'MACDh_12_26_9')
        if macd_val is not None:
            low, high = thresholds['MACD']
            scores['MACD'] = normalize_indicator(macd_val, low, high, bullish_is_high=True)
        else:
            scores['MACD'] = 50.0
            notes.append("MACD could not be calculated (NaN or missing).")

        # --- RSI & Stochastic ---
        rsi = safe_latest_value(hist, 'RSI_14')
        if rsi is not None:
            low, high = thresholds['RSI']
            scores['RSI'] = normalize_indicator(rsi, low, high, bullish_is_high=False)
        else:
            scores['RSI'] = 50.0
            notes.append("RSI could not be calculated (NaN or missing).")

        stoch = safe_latest_value(hist, 'STOCHk_14_3_3')
        if stoch is not None:
            low, high = thresholds['Stoch']
            scores['Stoch'] = normalize_indicator(stoch, low, high, bullish_is_high=False)
        else:
            scores['Stoch'] = 50.0
            notes.append("Stochastic could not be calculated.")

        # --- ADX ---
        adx = safe_latest_value(hist, 'ADX_14')
        if adx is not None:
            low, high = thresholds['ADX']
            scores['ADX_Strength'] = normalize_indicator(adx, low, high, bullish_is_high=True)
        else:
            scores['ADX_Strength'] = 50.0
            notes.append("ADX could not be calculated.")

        # --- ATR ---
        atr_val = safe_latest_value(hist, 'ATR_14')
        close_price = safe_latest_value(hist, 'close')
        if atr_val is not None and close_price:
            atr_percent = (atr_val / close_price) * 100
            low, high = thresholds['ATR']
            scores['ATR_Vol'] = normalize_volatility(atr_percent, low, high)
        else:
            scores['ATR_Vol'] = 50.0
            notes.append("ATR Volatility could not be calculated.")


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
            "indicators": {k: f"{v:.1f}/100" for k, v in scores.items()}
        }

    except Exception as e:
        logger.error(f"Failed to perform TA for {ticker}: {e}", exc_info=True)
        return {"error": f"Could not perform TA. Error: {e}"}