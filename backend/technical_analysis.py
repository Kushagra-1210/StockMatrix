# backend/technical_analysis.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from backend.data_fetcher import get_ticker_data
import pandas_ta as ta


logger = logging.getLogger(__name__)

# --- INDUSTRY BENCHMARK ZONES ---
INDUSTRY_THRESHOLDS = {
    'default': {'RSI': (40, 60), 'Stoch': (40, 60), 'MACD': (-0.15, 0.15), 'ADX': (20, 25), 'ATR': (1.5, 7.0)},
    'Energy': {'RSI': (35, 65), 'Stoch': (35, 65), 'MACD': (-0.25, 0.25), 'ADX': (18, 28), 'ATR': (2.0, 8.0)},
    'FMCG': {'RSI': (45, 55), 'Stoch': (45, 55), 'MACD': (-0.1, 0.1), 'ADX': (15, 22), 'ATR': (1.0, 4.0)},
    'Banking': {'RSI': (38, 62), 'Stoch': (38, 62), 'MACD': (-0.2, 0.2), 'ADX': (22, 30), 'ATR': (1.8, 6.0)}
}

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


# --- MAIN ANALYSIS FUNCTION ---
def analyze_technical_indicators(ticker: str, industry: str = 'default', basis: str = "annual") -> dict:
    try:
        thresholds = get_thresholds(industry)
        ticker_data = get_ticker_data(ticker)
        if "error" in ticker_data: return ticker_data
        if not isinstance(ticker_data, dict) or "history" not in ticker_data or not ticker_data["history"]:
            return {"error": "❌ No valid historical data for TA."}

        hist = pd.DataFrame(ticker_data["history"])
        hist['Date'] = pd.to_datetime(hist['Date'])
        hist.set_index('Date', inplace=True)
        # Rename columns for pandas_ta compatibility
        hist.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)

        # --- Use pandas_ta to calculate only the required indicators ---
        custom_strategy = ta.Strategy(
            name="Custom TA Strategy",
            description="Calculates only the indicators required for the analysis.",
            ta=[
                {"kind": "sma", "length": 50},
                {"kind": "sma", "length": 200},
                {"kind": "macd", "fast": 12, "slow": 26, "signal": 9},
                {"kind": "rsi", "length": 14},
                {"kind": "stoch", "k": 14, "d": 3, "smooth_k": 3},
                {"kind": "adx", "length": 14},
                {"kind": "atr", "length": 14},
                {"kind": "obv"},
            ]
        )
        hist.ta.strategy(custom_strategy)

        notes, scores = [], {}

        # --- SMA Trend ---
        if 'SMA_50' in hist.columns and 'SMA_200' in hist.columns:
            price = hist['close'].iloc[-1]
            sma50 = hist['SMA_50'].iloc[-1]
            sma200 = hist['SMA_200'].iloc[-1]
            if price > sma50 > sma200: scores['SMA_Trend'] = 100.0
            elif sma50 > price > sma200: scores['SMA_Trend'] = 70.0
            elif sma50 > sma200: scores['SMA_Trend'] = 60.0
            elif price < sma50 < sma200: scores['SMA_Trend'] = 0.0
            elif sma50 < price < sma200: scores['SMA_Trend'] = 30.0
            else: scores['SMA_Trend'] = 50.0
        else:
            scores['SMA_Trend'] = 50.0; notes.append("SMA trend could not be calculated.")

        # --- MACD ---
        if 'MACDh_12_26_9' in hist.columns:
            latest_hist = hist['MACDh_12_26_9'].iloc[-1]
            low, high = thresholds['MACD']
            scores['MACD'] = normalize_indicator(latest_hist, low, high, bullish_is_high=True)
        else:
            scores['MACD'] = 50.0; notes.append("MACD could not be calculated.")

        # --- RSI & Stochastic ---
        if 'RSI_14' in hist.columns:
            rsi = hist['RSI_14'].iloc[-1]
            low, high = thresholds['RSI']
            scores['RSI'] = normalize_indicator(rsi, low, high, bullish_is_high=False)
        else:
            scores['RSI'] = 50.0; notes.append("RSI could not be calculated.")

        if 'STOCHk_14_3_3' in hist.columns:
            stoch = hist['STOCHk_14_3_3'].iloc[-1]
            low, high = thresholds['Stoch']
            scores['Stoch'] = normalize_indicator(stoch, low, high, bullish_is_high=False)
        else:
            scores['Stoch'] = 50.0; notes.append("Stochastic could not be calculated.")

        # --- ADX ---
        if 'ADX_14' in hist.columns:
            adx = hist['ADX_14'].iloc[-1]
            low, high = thresholds['ADX']
            scores['ADX_Strength'] = normalize_indicator(adx, low, high, bullish_is_high=True)
        else:
            scores['ADX_Strength'] = 50.0; notes.append("ADX could not be calculated.")

        # --- ATR ---
        if 'ATRr_14' in hist.columns:
            atr_percent = hist['ATRr_14'].iloc[-1]
            low, high = thresholds['ATR']
            scores['ATR_Vol'] = normalize_volatility(atr_percent, low, high)
        else:
            scores['ATR_Vol'] = 50.0; notes.append("ATR Volatility could not be calculated.")

        # --- OBV ---
        if 'OBV' in hist.columns:
            obv_series = hist['OBV'].tail(10)
            if len(obv_series) > 1 and obv_series.iloc[-1] != obv_series.iloc[0]:
                scores['OBV_Trend'] = 100.0 if obv_series.iloc[-1] > obv_series.iloc[0] else 0.0
            else:
                scores['OBV_Trend'] = 50.0
        else:
            scores['OBV_Trend'] = 50.0; notes.append("OBV trend could not be calculated.")

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