import yfinance as yf
import numpy as np
import pandas as pd

def calculate_rsi(prices, period: int = 14):
    if prices is None or len(prices) < period:
        return None
    prices = pd.Series(prices)
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 2) if not np.isnan(rsi.iloc[-1]) else None

def analyze_technical_indicators(ticker: str, basis: str = "annual") -> dict:
    print(f"TA basis = {basis}")
    try:
        # Dynamic periods based on analysis basis
        if basis == "quarterly":
            period = "3mo"
            rsi_period = 7
            ma_period = 10
        else:  # annual
            period = "12mo"
            rsi_period = 14
            ma_period = 20

        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty or "Close" not in hist.columns or len(hist) < 30:
            return {"error": "Not enough data for TA."}

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]
        open_ = hist["Open"]
        current_price = close.iloc[-1]

        # Calculate indicators with dynamic periods
        rsi = calculate_rsi(close, rsi_period)
        sma = close.rolling(window=ma_period).mean().iloc[-1]
        ema = close.ewm(span=ma_period).mean().iloc[-1]

        # MACD (uses dynamic periods)
        ema_short = close.ewm(span=12 if basis == "annual" else 8).mean()
        ema_long = close.ewm(span=26 if basis == "annual" else 17).mean()
        macd_line = ema_short - ema_long
        signal_line = macd_line.ewm(span=9).mean()

        # Bollinger Bands (dynamic period)
        ma = close.rolling(window=ma_period).mean()
        std = close.rolling(window=ma_period).std()
        upper_band = ma + 2 * std
        lower_band = ma - 2 * std

        # Fibonacci (same calculation, different price history)
        fib_618 = high.max() - 0.618 * (high.max() - low.min())

        # Scoring (same weights, different calculations)
        total_score = 0
        total_possible = 0
        ta_breakdown = {}

        # 1. Trend (20%)
        try:
            avg_price = close.mean()
            trend_score = 20 if current_price > avg_price else 10
            total_score += trend_score
            total_possible += 20
            ta_breakdown["Trend vs Average Price (20%)"] = trend_score
        except:
            ta_breakdown["Trend vs Average Price (20%)"] = "N/A"

        # 2. Moving Averages (15%)
        try:
            ma_score = 15 if current_price > sma and current_price > ema else 7
            total_score += ma_score
            total_possible += 15
            ta_breakdown["SMA & EMA Signals (15%)"] = ma_score
        except:
            ta_breakdown["SMA & EMA Signals (15%)"] = "N/A"

        # 3. RSI (15%)
        try:
            if rsi is not None:
                rsi_score = 15 if 45 < rsi < 70 else 7
                total_score += rsi_score
                total_possible += 15
                ta_breakdown["RSI (15%)"] = rsi_score
            else:
                ta_breakdown["RSI (15%)"] = "N/A"
        except:
            ta_breakdown["RSI (15%)"] = "N/A"

        # 4. MACD (12%)
        try:
            macd_score = 12 if macd_line.iloc[-1] > signal_line.iloc[-1] else 6
            total_score += macd_score
            total_possible += 12
            ta_breakdown["MACD Signal (12%)"] = macd_score
        except:
            ta_breakdown["MACD Signal (12%)"] = "N/A"

        # 5. Volume Confirmation (10%)
        try:
            vol_score = 10 if volume.iloc[-1] > volume.mean() else 5
            total_score += vol_score
            total_possible += 10
            ta_breakdown["Volume Confirmation (10%)"] = vol_score
        except:
            ta_breakdown["Volume Confirmation (10%)"] = "N/A"

        # 6. Support & Resistance (8%)
        try:
            support = close.min()
            resistance = close.max()
            dist = (current_price - support) / (resistance - support)
            sr_score = 8 if dist < 0.3 else 4
            total_score += sr_score
            total_possible += 8
            ta_breakdown["Support & Resistance Range (8%)"] = sr_score
        except:
            ta_breakdown["Support & Resistance Range (8%)"] = "N/A"

        # 7. Candlestick Pattern (6%)
        try:
            if close.iloc[-1] > open_.iloc[-1] and close.iloc[-2] < open_.iloc[-2]:
                candle_score = 6
            else:
                candle_score = 3
            total_score += candle_score
            total_possible += 6
            ta_breakdown["Candlestick Pattern (6%)"] = candle_score
        except:
            ta_breakdown["Candlestick Pattern (6%)"] = "N/A"

        # 8. Bollinger Bands (5%)
        try:
            bollinger_score = 5 if lower_band.iloc[-1] < current_price < upper_band.iloc[-1] else 3
            total_score += bollinger_score
            total_possible += 5
            ta_breakdown["Bollinger Band Position (5%)"] = bollinger_score
        except:
            ta_breakdown["Bollinger Band Position (5%)"] = "N/A"

        # 9. Fibonacci Level (5%)
        try:
            fib_score = 5 if abs(current_price - fib_618) / current_price < 0.03 else 2
            total_score += fib_score
            total_possible += 5
            ta_breakdown["Fibonacci 61.8% Level (5%)"] = fib_score
        except:
            ta_breakdown["Fibonacci 61.8% Level (5%)"] = "N/A"

        # 10. Market Breadth Proxy (4%) — static
        try:
            breadth_score = 4
            total_score += breadth_score
            total_possible += 4
            ta_breakdown["Market Breadth Proxy (4%)"] = breadth_score
        except:
            ta_breakdown["Market Breadth Proxy (4%)"] = "N/A"

        if total_possible == 0:
            return {"error": "No technical indicators could be calculated."}

        ta_score = round((total_score / total_possible) * 100, 2)
        verdict = "Strong Buy" if ta_score >= 80 else "Buy" if ta_score >= 65 else "Hold" if ta_score >= 50 else "Sell"

        return {
            "current_price": round(current_price, 2),
            "rsi": rsi if isinstance(rsi, float) else "N/A",
            "sma_20": round(sma, 2) if isinstance(sma, float) else "N/A",
            "ema_20": round(ema, 2) if isinstance(ema, float) else "N/A",
            "ta_score": ta_score,
            "verdict": verdict,
            "period": basis.title(),
            "ta_breakdown": ta_breakdown
        }

    except Exception as e:
        return {"error": f"Technical analysis failed: {str(e)}"}