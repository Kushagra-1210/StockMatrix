# backend/technical_analysis.py
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import logging

logger = logging.getLogger(__name__)

# --- Helper functions to normalize indicator values to a 0-10 scale ---

def _normalize_rsi_stoch(value):
    """Normalizes RSI/Stochastic. Lower values (oversold) get a higher score."""
    if pd.isna(value): return 5 # Neutral score for no data
    # Invert the scale: 0-30 is bullish (score 10-7), 70-100 is bearish (score 3-0)
    if value < 30:
        return 7 + (30 - value) / 10  # Score between 7 and 10
    if value > 70:
        return 3 - (value - 70) / 10  # Score between 0 and 3
    # Neutral zone
    return 3 + (70 - value) / 10 * 0.1 # Score between 3 and 7

def _normalize_momentum(value):
    """Normalizes a momentum value that can be positive or negative."""
    if pd.isna(value): return 5
    # Assuming momentum values are typically within a certain range, we cap them.
    # A positive momentum is bullish.
    score = 5 + (value / 10) # Simple scaling, centered around 5
    return max(0, min(10, score)) # Ensure score is within 0-10

def _normalize_volatility(value, price):
    """Normalizes volatility indicators like BBW and ATR. Lower volatility is often a setup for a breakout."""
    if pd.isna(value) or price == 0: return 5
    # Express volatility as a percentage of the price
    vol_pct = (value / price) * 100
    # Lower volatility percentage gets a higher score (e.g., a tight squeeze)
    # A 5% volatility is considered high, gets a low score.
    score = 10 - (vol_pct * 2)
    return max(0, min(10, score))

# --- Main Analysis Function ---

def analyze_technical_indicators(ticker: str, basis: str = "annual") -> dict:
    """
    Analyzes technical indicators using a 10-factor model.
    The timeframe is fixed to 200 days as per the model's requirements.
    """
    try:
        # 1. Collect Input Data
        hist = yf.Ticker(ticker).history(period="200d")
        if hist.empty:
            return {"error": "No historical data found for the ticker."}

        # 2. Calculate All 10 Indicators using pandas_ta
        custom_strategy = ta.Strategy(
            name="10-Factor Model",
            description="SMA, MACD, RSI, STOCH, MOM, ATR, BBANDS, OBV, VO, ADX",
            ta=[
                {"kind": "sma", "length": 50},
                {"kind": "sma", "length": 200},
                {"kind": "macd", "fast": 12, "slow": 26, "signal": 9},
                {"kind": "rsi", "length": 14},
                {"kind": "stoch", "k": 14, "d": 3, "smooth_k": 3},
                {"kind": "mom", "length": 10},
                {"kind": "atr", "length": 14},
                {"kind": "bbands", "length": 20, "std": 2},
                {"kind": "obv"},
                {"kind": "vo", "fast": 5, "slow": 10},
                {"kind": "adx", "length": 14},
            ]
        )
        hist.ta.strategy(custom_strategy)

        # Get the latest values for all indicators
        latest = hist.iloc[-1]
        current_price = latest['Close']

        # 3. Score Calculation (0-10 for each)
        scores = {}
        
        # Trend Indicators
        scores['SMA'] = 10 if latest['SMA_50'] > latest['SMA_200'] else 0
        scores['MACD'] = 10 if latest['MACDh_12_26_9'] > 0 else 0

        # Momentum Indicators
        scores['RSI'] = _normalize_rsi_stoch(latest['RSI_14'])
        scores['Stoch'] = _normalize_rsi_stoch(latest['STOCHk_14_3_3'])
        scores['Momentum'] = _normalize_momentum(latest['MOM_10'])

        # Volatility Indicators
        scores['ATR'] = _normalize_volatility(latest['ATRr_14'], current_price)
        scores['BBW'] = _normalize_volatility(latest['BBB_20_2.0'], current_price)

        # Volume Indicators
        # OBV confirming trend (rising OBV is bullish)
        scores['OBV'] = 10 if hist['OBV'].diff().iloc[-1] > 0 else 0
        scores['VolumeOsc'] = 5 + latest['VO_5_10'] if not pd.isna(latest['VO_5_10']) else 5

        # Composite Indicator
        scores['ADX'] = 10 if latest['ADX_14'] > 25 else 0

        # 4. Final Score & Signal Generation
        final_score = np.mean(list(scores.values())) * 10
        
        if final_score >= 80: verdict = "Strong Buy"
        elif final_score >= 60: verdict = "Bullish"
        elif final_score >= 30: verdict = "Neutral"
        else: verdict = "Bearish"

        return {
            "ta_score": round(final_score, 2),
            "verdict": verdict,
            "period": "200-Day",
            # Include the breakdown for transparency
            "ta_breakdown": {k: f"{v:.1f}/10" for k, v in scores.items()}
        }

    except Exception as e:
        logger.error(f"Failed to perform advanced TA for {ticker}: {e}", exc_info=True)
        return {"error": f"Could not perform TA for {ticker}. Error: {e}"}