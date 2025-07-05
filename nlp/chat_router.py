from backend.technical_analysis import analyze_technical_indicators
from backend.fundamental_analysis import analyze_fundamentals
from backend.sentiment_analysis import analyze_sentiment
from backend.screener_engine import screen_stocks
from backend.news_risk_analyzer import fetch_news_risk
from backend.report_generator import generate_pdf_report, generate_csv_report
from backend.chat_assistant import get_chat_response
import yfinance as yf
from datetime import datetime

def handle_chat_command(command: str, ticker: str = None):
    command_lower = command.lower().strip()

    # 🎯 Screener Engine
    if "screener" in command_lower:
        return "Opening Screener Engine module for you.", None, None

    # 📄 Report Generator
    elif "report" in command_lower and ticker:
        ta = analyze_technical_indicators(ticker)
        fa = analyze_fundamentals(ticker)
        sentiment = analyze_sentiment(ticker)
        news_risk = fetch_news_risk(ticker)

        final_score = round(
            0.35 * fa["fa_score"] +
            0.35 * ta["ta_score"] +
            0.2 * sentiment["score"] * 10 +
            0.1 * news_risk["risk_score"], 2
        )
        final_verdict = (
            "Strong Buy" if final_score >= 80
            else "Buy" if final_score >= 65
            else "Hold" if final_score >= 50
            else "Sell"
        )

        stock = yf.Ticker(ticker)
        info = stock.info
        stock_info = {
            "ticker": ticker,
            "name": info.get("shortName", ""),
            "price": info.get("currentPrice", "N/A"),
            "date": datetime.now().strftime("%Y-%m-%d"),
        }

        chat_summary = get_chat_response(stock_info, ta, fa, sentiment, news_risk, final_score, final_verdict)

        return chat_summary, None, {
            "stock_info": stock_info,
            "ta": ta, "fa": fa,
            "sentiment": sentiment,
            "news_risk": news_risk,
            "final_score": final_score,
            "final_verdict": final_verdict
        }

    # 🧪 Analyze Command
    elif "analyze" in command_lower and ticker:
        ta = analyze_technical_indicators(ticker)
        fa = analyze_fundamentals(ticker)
        sentiment = analyze_sentiment(ticker)
        summary = f"Analysis complete for {ticker}. TA Score: {ta['ta_score']}, FA Score: {fa['fa_score']}, Sentiment: {sentiment['label']}"
        return summary, None, {
            "ta": ta, "fa": fa, "sentiment": sentiment
        }

    # 💬 ChatGPT-style fallback (for general financial questions)
    else:
        return (
            "⚠️ Sorry, I can only help with:\n\n"
            "- Run Analysis (RA)\n"
            "- Screener Engine (SE)\n"
            "- Generate Report (GR)\n\n"
            "Please type one of these to continue.",
            None,
            None
        )
