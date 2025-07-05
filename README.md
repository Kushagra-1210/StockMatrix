# 📊 StockMatrix: AI-Powered Stock Analyzer

**StockMatrix** is a smart, AI-powered web app that analyzes the **top 50 stocks** from 5 major global exchanges:  
**NSE, NYSE, LSE, HKEX, and TSE**, using a combination of:

- 📉 Technical Analysis  
- 📈 Fundamental Analysis  
- 💬 Sentiment Analysis  
- 🛡️ News & Risk Analysis  

The app is entirely **chatbot-driven**, making stock analysis interactive, intuitive, and intelligent.

---

## 🚀 Features

### 🤖 AI Chat Assistant
- Chat-first interface (no sidebar)
- Accepts commands like: `RA` (Run Analysis), `GR` (Generate Report), `IG` (Insight Generation)
- Context-aware follow-up support
- Routes to modules automatically

---

### 🔍 Run Analysis
- Select stock exchange and ticker
- Choose basis: **Quarterly or Annual**
- Run:
  - Technical Analysis (TA)
  - Fundamental Analysis (FA)
  - Both + Sentiment + News Risk
- Shows breakdown and final investment verdict  
- Auto-refresh live prices option
- Shows **source** under each section

---

### 📊 Screener Engine
- Filters stocks based on:
  - Minimum TA Score
  - Minimum FA Score
  - Maximum Volatility
- Shows matched stocks in a table
- Allows CSV download of results

---

### 📄 Report Generator
- Select any stock
- Generates:
  - 📄 PDF Report (detailed)
  - 📈 CSV Report (raw scores)
- Includes TA, FA, Sentiment, News, and Final Score

---

### 🏆 Stock Leaderboard
- Explore the top 5 stocks across:
  - Strong Buys
  - Undervalued Stocks
  - Bullish Momentum
  - Low Risk
  - High Volatility
  - Negative Sentiment
  - Midcap Opportunities

---

## 📚 Data Sources

| Analysis Type         | Source                                               |
|-----------------------|------------------------------------------------------|
| Technical Analysis    | Yahoo Finance Historical Price Data via `yfinance`  |
| Fundamental Analysis  | Yahoo Finance Financial Data via `yfinance`         |
| Sentiment Analysis    | Google News RSS + VADER + TextBlob                  |
| News & Risk Analysis  | Simulated Risk Signals (Based on Google News RSS)   |

*Sources are automatically shown under each section in the app (in small font).*

---

## 🧰 Tech Stack

- **Frontend:** Streamlit  
- **Backend:** Python (`yfinance`, `vaderSentiment`, `textblob`, `plotly`)  
- **AI Routing & Logic:** OpenAI (Chat Command Routing)  
- **Deployment:** GitHub + Streamlit Cloud (or custom server)

---

## 🗂️ Project Structure

STOCK_ANALYSER/
├── app/
│ └── main.py ← Chatbot UI
├── backend/
│ ├── technical_analysis.py
│ ├── fundamental_analysis.py
│ ├── sentiment_analysis.py
│ ├── news_risk_analyzer.py
│ ├── screener_engine.py
│ ├── report_generator.py
│ └── market_selector.py
├── nlp/
│ └── chat_router.py
├── README.md
└── .gitignore

---

## 👤 Author

**Kushagra Bansal**  
GitHub: [@Kushagra-1210](https://github.com/Kushagra-1210)
LinkedIn:(https://www.linkedin.com/in/kushagra-kb1210/)

## ⚠️ Disclaimer

StockMatrix is an academic and portfolio project.  
It is **not intended for financial advice or investment decisions**. Use responsibly.

