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
    try:
        period = "12mo" if basis == "annual" else "3mo"
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
            sma_20 = close.rolling(window=20).mean().iloc[-1]
            ema_20 = close.ewm(span=20).mean().iloc[-1]
            ma_score = 15 if current_price > sma_20 and current_price > ema_20 else 7
            total_score += ma_score
            total_possible += 15
            ta_breakdown["SMA & EMA Signals (15%)"] = ma_score
        except:
            sma_20 = ema_20 = "N/A"
            ta_breakdown["SMA & EMA Signals (15%)"] = "N/A"

        # 3. RSI (15%)
        try:
            rsi = calculate_rsi(close)
            if rsi is not None:
                rsi_score = 15 if 45 < rsi < 70 else 7
                total_score += rsi_score
                total_possible += 15
                ta_breakdown["RSI (15%)"] = rsi_score
            else:
                ta_breakdown["RSI (15%)"] = "N/A"
        except:
            rsi = "N/A"
            ta_breakdown["RSI (15%)"] = "N/A"

        # 4. MACD (12%)
        try:
            ema_12 = close.ewm(span=12).mean()
            ema_26 = close.ewm(span=26).mean()
            macd_line = ema_12 - ema_26
            signal_line = macd_line.ewm(span=9).mean()
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
            ma = close.rolling(window=20).mean()
            std = close.rolling(window=20).std()
            upper = ma + 2 * std
            lower = ma - 2 * std
            bollinger_score = 5 if lower.iloc[-1] < current_price < upper.iloc[-1] else 3
            total_score += bollinger_score
            total_possible += 5
            ta_breakdown["Bollinger Band Position (5%)"] = bollinger_score
        except:
            ta_breakdown["Bollinger Band Position (5%)"] = "N/A"

        # 9. Fibonacci Level (5%)
        try:
            high_ = high.max()
            low_ = low.min()
            fib_618 = high_ - 0.618 * (high_ - low_)
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
            "sma_20": round(sma_20, 2) if isinstance(sma_20, float) else "N/A",
            "ema_20": round(ema_20, 2) if isinstance(ema_20, float) else "N/A",
            "ta_score": ta_score,
            "verdict": verdict,
            "ta_breakdown": ta_breakdown
        }

    except Exception as e:
        return {"error": f"Technical analysis failed: {str(e)}"}
