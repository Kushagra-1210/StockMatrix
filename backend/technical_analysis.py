# backend/technical_analysis.py

import yfinance as yf
import pandas_ta as ta
import logging

def analyze_technical_indicators(ticker: str, basis: str = "annual") -> dict:
    """
    Analyzes technical indicators for a stock using a more robust and clean approach.

    This function will raise an error if the historical data cannot be fetched,
    allowing the calling function (e.g., screener_engine) to handle the exception.
    """
    if basis.lower() not in ("annual", "quarterly"):
        return {"error": f"Invalid basis '{basis}'. Must be 'annual' or 'quarterly'"}

    try:
        # 1. --- Data Fetching ---
        period = "1y" if basis.lower() == "annual" else "6mo"
        hist = yf.Ticker(ticker).history(period=period)

        if hist.empty:
            logging.warning(f"No historical data found for {ticker} for the period {period}.")
            return {"error": "No historical data found for the given period."}

        # 2. --- Indicator Calculations ---
        # Use pandas_ta to append all indicators to the dataframe at once.
        custom_ta_strategy = ta.Strategy(
            name="StockMatrix TA",
            description="SMA, EMA, RSI, and MACD",
            ta=[
                {"kind": "sma", "length": 20},
                {"kind": "ema", "length": 20},
                {"kind": "rsi"},
                {"kind": "macd"},
            ]
        )
        hist.ta.strategy(custom_ta_strategy)

        # Get the most recent row of data with all indicators
        latest = hist.iloc[-1]
        
        # --- Safely get the latest values ---
        current_price = latest.get('Close')
        rsi = latest.get('RSI_14')
        sma_20 = latest.get('SMA_20')
        ema_20 = latest.get('EMA_20')
        macd_line = latest.get('MACD_12_26_9')
        macd_signal = latest.get('MACDs_12_26_9')

        # 3. --- Scoring ---
        score = 0
        total_weight = 0
        ta_breakdown = {}

        # Trend vs Moving Averages (50%)
        if all(v is not None for v in [current_price, sma_20, ema_20]):
            total_weight += 50
            trend_score = 0
            if current_price > sma_20:
                trend_score += 25
            if current_price > ema_20:
                trend_score += 25
            score += trend_score
            ta_breakdown["Trend (SMA & EMA)"] = f"{trend_score}/50"

        # Momentum - RSI (25%)
        if rsi is not None:
            total_weight += 25
            rsi_score = 0
            if rsi > 70: rsi_score = 5
            elif rsi < 30: rsi_score = 25
            else: rsi_score = 15
            score += rsi_score
            ta_breakdown["RSI Momentum"] = f"{rsi_score}/25"

        # Momentum - MACD (25%)
        if all(v is not None for v in [macd_line, macd_signal]):
            total_weight += 25
            macd_score = 5
            if macd_line > macd_signal:
                macd_score = 25
            score += macd_score
            ta_breakdown["MACD"] = f"{macd_score}/25"

        # Final Score & Verdict
        ta_score = (score / total_weight) * 100 if total_weight > 0 else 0
        verdict = "Bullish" if ta_score >= 65 else "Bearish" if ta_score < 40 else "Neutral"

        return {
            "current_price": round(current_price, 2) if current_price is not None else "N/A",
            "rsi": round(rsi, 2) if rsi is not None else "N/A",
            "sma_20": round(sma_20, 2) if sma_20 is not None else "N/A",
            "ema_20": round(ema_20, 2) if ema_20 is not None else "N/A",
            "ta_score": round(ta_score, 2),
            "verdict": verdict,
            "period": basis.title(),
            "ta_breakdown": ta_breakdown
        }

    except Exception as e:
        logging.error(f"Failed to perform technical analysis for {ticker}: {e}", exc_info=True)
        return {"error": f"Could not perform TA for {ticker}. Error: {e}"}