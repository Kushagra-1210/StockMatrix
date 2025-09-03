# backend/technical_analysis.py
import pandas as pd
import numpy as np
import logging
from backend.data_provider import DataProvider
import pandas_ta as ta

logger = logging.getLogger(__name__)

# --- INDUSTRY BENCHMARK ZONES ---
# These are used for generating the internal scores, not for display.
INDUSTRY_THRESHOLDS = {
    'default': {'MACD': (-0.15, 0.15), 'ADX': (20, 25), 'ATR': (1.5, 7.0)},
    'Energy': {'MACD': (-0.25, 0.25), 'ADX': (18, 28), 'ATR': (2.0, 8.0)},
    'FMCG': {'MACD': (-0.1, 0.1), 'ADX': (15, 22), 'ATR': (1.0, 4.0)},
    'Banking': {'MACD': (-0.2, 0.2), 'ADX': (22, 30), 'ATR': (1.8, 6.0)}
}

# --- NORMALIZATION HELPERS ---
def get_thresholds(industry: str):
    return INDUSTRY_THRESHOLDS.get(industry, INDUSTRY_THRESHOLDS['default'])

def normalize_momentum(value, neutral_low, neutral_high):
    if pd.isna(value): return 50.0
    if value > neutral_high:
        score = 75 + min(25, (value - neutral_high) * 5)
    elif value < neutral_low:
        score = 25 - min(25, (neutral_low - value) * 5)
    else:
        score = 25 + ((value - neutral_low) / (neutral_high - neutral_low)) * 50.0
    return max(0.0, min(100.0, score))

def normalize_oscillator(value, oversold=30, overbought=70):
    if pd.isna(value): return 50.0
    if value < oversold:
        return 75 + min(25, (oversold - value) * 1.5)
    elif value > overbought:
        return 25 - min(25, (value - overbought) * 1.5)
    else:
        return 25 + ((value - oversold) / (overbought - oversold)) * 50.0

def normalize_volatility(vol_percent, low=1.5, high=7.0):
    if pd.isna(vol_percent): return 50.0
    score = 100 - ((vol_percent - low) / (high - low)) * 100
    return max(0.0, min(100.0, score))

def safe_latest_value(df, column_name):
    if column_name in df.columns:
        series = df[column_name].dropna()
        if not series.empty:
            return series.iloc[-1]
    return np.nan

# --- MAIN ANALYSIS FUNCTION ---
def analyze_technical_indicators(ticker: str, industry: str = 'default', basis: str = "annual") -> dict:
    try:
        provider = DataProvider(ticker)
        thresholds = get_thresholds(industry)
        hist = provider.get_history()

        if hist.empty:
            return {"error": "❌ No valid historical data for TA."}

        # --- Data Preparation ---
        hist['Date'] = pd.to_datetime(hist['Date'])
        hist.set_index('Date', inplace=True)
        hist.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
        
        # --- Indicator Calculations using Standard Parameters ---
        hist.ta.rsi(length=14, append=True)
        hist.ta.macd(fast=12, slow=26, signal=9, append=True)
        hist.ta.stoch(k=14, d=3, smooth_k=3, append=True)
        hist.ta.adx(length=14, append=True)
        hist.ta.atr(length=14, append=True)
        hist.ta.obv(append=True)
        hist.ta.sma(length=50, append=True)
        hist.ta.sma(length=200, append=True)

        # --- Store RAW VALUES for UI Display ---
        raw_values = {
            'RSI': safe_latest_value(hist, 'RSI_14'),
            # --- THIS IS THE FIX ---
            'Stoch': safe_latest_value(hist, 'STOCHd_14_3_3'), # Using the smoother %D line
            'MACD': safe_latest_value(hist, 'MACDh_12_26_9'),
            'ADX': safe_latest_value(hist, 'ADX_14'),
            'ATR': safe_latest_value(hist, 'ATR_14'),
            'OBV': safe_latest_value(hist, 'OBV'),
            'SMA_50': safe_latest_value(hist, 'SMA_50'),
            'SMA_200': safe_latest_value(hist, 'SMA_200'),
            'Price': safe_latest_value(hist, 'close')
        }

        # --- Calculate SCORES for Internal Logic ---
        scores = {}
        notes = []

        # SMA Trend Score
        if all(pd.notna(raw_values[k]) for k in ['Price', 'SMA_50', 'SMA_200']):
            price, sma50, sma200 = raw_values['Price'], raw_values['SMA_50'], raw_values['SMA_200']
            if price > sma50 > sma200: scores['SMA_Trend'] = 100.0
            elif price > sma50 and price > sma200: scores['SMA_Trend'] = 70.0
            elif price < sma50 < sma200: scores['SMA_Trend'] = 0.0
            else: scores['SMA_Trend'] = 50.0
        else:
            scores['SMA_Trend'] = 50.0
            notes.append("SMA trend could not be calculated.")

        # Other Scores
        scores['MACD'] = normalize_momentum(raw_values['MACD'], thresholds['MACD'][0], thresholds['MACD'][1])
        scores['RSI'] = normalize_oscillator(raw_values['RSI'], 30, 70)
        scores['Stoch'] = normalize_oscillator(raw_values['Stoch'], 20, 80)
        scores['ADX_Strength'] = normalize_momentum(raw_values['ADX'], thresholds['ADX'][0], thresholds['ADX'][1])
        
        atr_percent = (raw_values['ATR'] / raw_values['Price']) * 100 if pd.notna(raw_values['ATR']) and pd.notna(raw_values['Price']) and raw_values['Price'] != 0 else np.nan
        scores['ATR_Vol'] = normalize_volatility(atr_percent, thresholds['ATR'][0], thresholds['ATR'][1])
        # Debug ATR calculation if missing
        if pd.isna(raw_values['ATR']):
            notes.append(f"ATR (14) is missing. hist columns: {list(hist.columns)}. Row count: {len(hist)}. Sample ATR values: {hist['ATR_14'].dropna().tail(5).to_list() if 'ATR_14' in hist.columns else 'ATR_14 not in columns'}.")
        
        obv_series = hist['OBV'].dropna().tail(10)
        if len(obv_series) > 1 and obv_series.iloc[-1] != obv_series.iloc[0]:
            scores['OBV_Trend'] = 100.0 if obv_series.iloc[-1] > obv_series.iloc[0] else 0.0
        else:
            scores['OBV_Trend'] = 50.0

        # --- Final Score & Verdict ---
        final_score = np.mean(list(scores.values()))
        if final_score >= 80: verdict = "🚀 Strong Buy"
        elif final_score >= 65: verdict = "✅ Buy"
        elif final_score >= 55: verdict = "🟢 Cautiously Optimistic"
        elif final_score >= 45: verdict = "🟡 Neutral"
        else: verdict = "🔴 Sell"

        # --- Format Raw Values for Display ---
        display_values = {k: f"{v:.2f}" if pd.notna(v) else "N/A" for k, v in raw_values.items()}
        
        methodology_note = "Note: Values are calculated using standard formulas on end-of-day data. Minor discrepancies with other platforms may occur due to differences in data sources or calculation nuances."

        return {
            "ta_score": round(final_score, 2),
            "verdict": verdict,
            "notes": notes,
            "indicators": display_values,
            "scores": {k: f"{v:.1f}/100" for k, v in scores.items()},
            "methodology_note": methodology_note
        }

    except Exception as e:
        logger.error(f"Failed to perform TA for {ticker}: {e}", exc_info=True)
        return {"error": f"Could not perform TA. Error: {e}"}
