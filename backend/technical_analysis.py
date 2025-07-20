# backend/technical_analysis.py

import yfinance as yf
import pandas as pd
import logging

def _calculate_sma(data: pd.Series, period: int = 20) -> pd.Series:
    """Calculates the Simple Moving Average (SMA)."""
    return data.rolling(window=period).mean()

def _calculate_ema(data: pd.Series, period: int = 20) -> pd.Series:
    """Calculates the Exponential Moving Average (EMA)."""
    return data.ewm(span=period, adjust=False).mean()

def _calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """Calculates the Relative Strength Index (RSI)."""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # Handle division by zero
    if loss.iloc[-1] == 0:
        return pd.Series([100] * len(data)) # If no losses, RSI is 100
        
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def _calculate_macd(data: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
    """Calculates the Moving Average Convergence Divergence (MACD)."""
    fast_ema = data.ewm(span=fast_period, adjust=False).mean()
    slow_ema = data.ewm(span=slow_period, adjust=False).mean()
    
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    return macd_line, signal_line

def analyze_technical_indicators(ticker: str, basis: str = "annual") -> dict:
    """
    Analyzes technical indicators for a stock using only pandas for calculations.
    """
    if basis.lower() not in ("annual", "quarterly"):
        return {"error": f"Invalid basis '{basis}'. Must be 'annual' or 'quarterly'"}

    try:
        period = "1y" if basis.lower() == "annual" else "6mo"
        hist = yf.Ticker(ticker).history(period=period)

        if hist.empty or "Close" not in hist:
            return {"error": "No historical data with 'Close' prices found."}

        close_prices = hist['Close']

        # --- Indicator Calculations ---
        # Get the latest (last) value for each indicator
        rsi = _calculate_rsi(close_prices).iloc[-1]
        sma_20 = _calculate_sma(close_prices).iloc[-1]
        ema_20 = _calculate_ema(close_prices).iloc[-1]
        macd_line, macd_signal = _calculate_macd(close_prices)
        macd_line_latest = macd_line.iloc[-1]
        macd_signal_latest = macd_signal.iloc[-1]
        current_price = close_prices.iloc[-1]

        # --- Scoring ---
        score = 0
        total_weight = 0
        ta_breakdown = {}

        # Trend vs Moving Averages (50%)
        if not pd.isna(current_price) and not pd.isna(sma_20) and not pd.isna(ema_20):
            total_weight += 50
            trend_score = 0
            if current_price > sma_20: trend_score += 25
            if current_price > ema_20: trend_score += 25
            score += trend_score
            ta_breakdown["Trend (SMA & EMA)"] = f"{trend_score}/50"

        # Momentum - RSI (25%)
        if not pd.isna(rsi):
            total_weight += 25
            rsi_score = 0
        # A more gradual scoring for RSI
        if rsi > 70:
            rsi_score = 25 - min((rsi - 70) * 1, 20)  # Penalize for being extremely overbought
        elif rsi < 30:
            rsi_score = min((30 - rsi) * 1, 20)      # Reward for being oversold
        else:
            rsi_score = 15  # Neutral
            score += rsi_score
            ta_breakdown["RSI Momentum"] = f"{rsi_score}/25"

        # Momentum - MACD (25%)
        if not pd.isna(macd_line_latest) and not pd.isna(macd_signal_latest):
            total_weight += 25
            macd_score = 5
            if macd_line_latest > macd_signal_latest:
                macd_score = 25
            score += macd_score
            ta_breakdown["MACD"] = f"{macd_score}/25"

        # Final Score & Verdict
        ta_score = (score / total_weight) * 100 if total_weight > 0 else 0
        verdict = "Bullish" if ta_score >= 65 else "Bearish" if ta_score < 40 else "Neutral"

        return {
            "current_price": round(current_price, 2) if not pd.isna(current_price) else "N/A",
            "rsi": round(rsi, 2) if not pd.isna(rsi) else "N/A",
            "sma_20": round(sma_20, 2) if not pd.isna(sma_20) else "N/A",
            "ema_20": round(ema_20, 2) if not pd.isna(ema_20) else "N/A",
            "ta_score": round(ta_score, 2),
            "verdict": verdict,
            "period": basis.title(),
            "ta_breakdown": ta_breakdown
        }

    except Exception as e:
        logging.error(f"Failed to perform technical analysis for {ticker}: {e}", exc_info=True)
        return {"error": f"Could not perform TA for {ticker}. Error: {e}"}