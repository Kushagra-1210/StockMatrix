# backend/technical_analysis.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from backend.data_fetcher import get_ticker_data
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)

# --- INDUSTRY BENCHMARK ZONES ---
INDUSTRY_THRESHOLDS = {
    'default': {
        'RSI': (40, 60),
        'Stoch': (40, 60),
        'MACD': (-0.15, 0.15),
        'ADX': (20, 25),
        'ATR': (1.5, 7.0)
    },
    'Energy': {
        'RSI': (35, 65),
        'Stoch': (35, 65),
        'MACD': (-0.25, 0.25),
        'ADX': (18, 28),
        'ATR': (2.0, 8.0)
    },
    'FMCG': {
        'RSI': (45, 55),
        'Stoch': (45, 55),
        'MACD': (-0.1, 0.1),
        'ADX': (15, 22),
        'ATR': (1.0, 4.0)
    },
    'Banking': {
        'RSI': (38, 62),
        'Stoch': (38, 62),
        'MACD': (-0.2, 0.2),
        'ADX': (22, 30),
        'ATR': (1.8, 6.0)
    }
    # Add more industry profiles as needed
}

# --- NORMALIZATION HELPERS ---
def get_thresholds(industry: str):
    return INDUSTRY_THRESHOLDS.get(industry, INDUSTRY_THRESHOLDS['default'])

def normalize_indicator(value, neutral_low, neutral_high, bullish_is_high=True):
    if pd.isna(value): return 5.0
    if value > neutral_high:
        score = 7.5 + min(2.5, (value - neutral_high) * 0.2)
        return score if bullish_is_high else 10 - score
    elif value < neutral_low:
        score = 2.5 - min(2.5, (neutral_low - value) * 0.2)
        return score if bullish_is_high else 10 - score
    else:
        return 2.5 + (value - neutral_low) / (neutral_high - neutral_low) * 5.0

def normalize_volatility(vol_percent, low=1.5, high=7.0):
    if pd.isna(vol_percent): return 5.0
    score = 10 - ((vol_percent - low) / (high - low)) * 10
    return max(0.0, min(10.0, score))

# --- CALCULATORS ---
def _calculate_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def _calculate_atr(high, low, close, length=14):
    tr1 = abs(high - low)
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return _calculate_ema(tr, span=length)

def _calculate_adx(high, low, close, length=14):
    dm_plus = high.diff()
    dm_minus = low.diff()
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

# --- MAIN FUNCTION ---
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

        notes, scores = [], {}
        close = hist['Close']; low = hist['Low']; high = hist['High']; volume = hist['Volume']

        # SMA Trend
        if len(hist) >= 200:
            price = close.iloc[-1]
            sma50 = close.rolling(window=50).mean()
            sma200 = close.rolling(window=200).mean()
            sma_slope_50 = LinearRegression().fit(np.arange(50).reshape(-1, 1), sma50.dropna().values[-50:]).coef_[0]
            sma_slope_200 = LinearRegression().fit(np.arange(200).reshape(-1, 1), sma200.dropna().values[-200:]).coef_[0]
            if price > sma50.iloc[-1] > sma200.iloc[-1] and sma_slope_50 > 0 and sma_slope_200 > 0:
                scores['SMA_Trend'] = 10.0
            elif sma50.iloc[-1] > price > sma200.iloc[-1] and sma_slope_50 > 0:
                scores['SMA_Trend'] = 7.0
            elif sma50.iloc[-1] > sma200.iloc[-1]:
                scores['SMA_Trend'] = 6.0
            elif price < sma50.iloc[-1] < sma200.iloc[-1] and sma_slope_50 < 0:
                scores['SMA_Trend'] = 0.0
            elif sma50.iloc[-1] < price < sma200.iloc[-1]:
                scores['SMA_Trend'] = 3.0
            else:
                scores['SMA_Trend'] = 5.0
        else:
            scores['SMA_Trend'] = 5.0
            notes.append("SMA trend could not be fully calculated.")

        # MACD
        if len(hist) >= 26:
            ema12 = _calculate_ema(close, 12)
            ema26 = _calculate_ema(close, 26)
            macd_line = ema12 - ema26
            signal_line = _calculate_ema(macd_line, 9)
            macd_hist = macd_line - signal_line
            latest_hist = macd_hist.iloc[-1]
            low, high = thresholds['MACD']
            scores['MACD'] = normalize_indicator(latest_hist, low, high, bullish_is_high=True)
        else:
            scores['MACD'] = 5.0
            notes.append("MACD could not be calculated.")

        # RSI & Stochastic
        if len(hist) >= 14:
            delta = close.diff()
            gain = delta.where(delta > 0, 0).ewm(span=14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(span=14, adjust=False).mean()
            rsi = 100 - (100 / (1 + (gain / (loss + 1e-6))))
            low, high = thresholds['RSI']
            scores['RSI'] = normalize_indicator(rsi.iloc[-1], low, high, bullish_is_high=False)

            low14 = low.rolling(14).min()
            high14 = high.rolling(14).max()
            stoch_k = 100 * (close - low14) / (high14 - low14 + 1e-6)
            low, high = thresholds['Stoch']
            scores['Stoch'] = normalize_indicator(stoch_k.iloc[-1], low, high, bullish_is_high=False)
        else:
            scores['RSI'] = 5.0; scores['Stoch'] = 5.0
            notes.append("RSI/Stochastic could not be calculated.")

        # ADX
        if len(hist) >= 28:
            adx = _calculate_adx(high, low, close, 14)
            low, high = thresholds['ADX']
            scores['ADX_Strength'] = normalize_indicator(adx, low, high, bullish_is_high=True)
        else:
            scores['ADX_Strength'] = 5.0
            notes.append("ADX could not be calculated.")

        # ATR
        if len(hist) >= 15:
            atr = _calculate_atr(high, low, close, 14).iloc[-1]
            atr_percent = (atr / close.iloc[-1]) * 100
            low, high = thresholds['ATR']
            scores['ATR_Vol'] = normalize_volatility(atr_percent, low, high)
        else:
            scores['ATR_Vol'] = 5.0
            notes.append("ATR Volatility could not be calculated.")

        # OBV
        if len(hist) >= 20 and 'Volume' in hist.columns:
            obv = (np.sign(close.diff()) * volume).cumsum()
            obv_recent = obv.tail(10).reset_index()
            obv_recent['t'] = range(len(obv_recent))
            try:
                reg = LinearRegression().fit(obv_recent[['t']], obv_recent[0])
                slope = reg.coef_[0]
                scores['OBV_Trend'] = 10.0 if slope > 0 else 0.0
            except Exception:
                scores['OBV_Trend'] = 5.0
                notes.append("OBV slope regression failed.")
        else:
            scores['OBV_Trend'] = 5.0
            notes.append("OBV trend could not be calculated.")

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
