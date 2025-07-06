# 📈 StockMatrix — AI-Powered Stock Analysis Platform

**StockMatrix** is a real-time, AI-powered web application that helps users evaluate global stocks through a unified lens of **Fundamental**, **Technical**, **Sentiment**, and **News-based Risk Analysis** — all accessible via a natural language chatbot interface.

🔗 **Live App:** [https://stockmatrix-kb.streamlit.app](https://stockmatrix-kb.streamlit.app)

---

## 💡 Problem It Solves

Retail investors often struggle to make informed decisions because:
- Data is scattered across platforms (e.g., price charts on one site, financials on another)
- There is no unified, structured scoring framework
- Market sentiment and risk headlines are missing from analysis
- Tools are too technical for casual investors

> **StockMatrix solves these issues by integrating multiple dimensions of analysis into one AI-assisted, easy-to-use platform.**

---

## 🚀 Key Features

| Feature                             | Status |
|------------------------------------|--------|
| 🧠 Fundamental Analysis             | ✅ 10-factor weighted model |
| 📉 Technical Analysis               | ✅ 10-factor weighted model |
| 💬 Sentiment Scoring                | ✅ Uses real-time Google News RSS headlines |
| 📰 News Risk Analysis               | ✅ Uses Marketaux API headlines with sector-aware scoring |
| 🏆 Stock Leaderboard (7 categories) | ✅ Top 5 picks by strategy |
| 📊 Screener Engine                  | ✅ Filter by FA/TA/Volatility |
| 🔄 Quarterly vs Annual Toggle       | ✅ Adjusts all analysis accordingly |
| 🗣️ AI Chatbot Interface             | ✅ Routes to features + follow-ups |
| 📁 Report Generator (PDF/CSV)       | ✅ Full report with analysis and headlines |
| 🧠 Headline-Based Sentiment + Risk  | ✅ Sentiment + Risk explained using real news headlines |

---

## 📂 How It Works

1. **Select a stock** from one of 5 exchanges (NSE, NYSE, LSE, HKEX, TSE)
2. Choose **quarterly or annual** data mode
3. Get a unified breakdown of:
   - 📉 Price Trends (RSI, SMA, EMA, etc.)
   - 📊 Financial Strength (ROE, PE, EPS, FCF, etc.)
   - 💬 Market Sentiment (real news headline scoring)
   - 📰 News Risk Score (sector-aware API-driven scoring)
4. View:
   - Combined investment score & verdict
   - Screener or leaderboard outputs
   - Downloadable report with embedded headlines

---

## 🧠 How News Risk Analysis Works

The updated **News Risk Analyzer** dynamically:
- Classifies the stock into a sector (Tech, Finance, Retail)
- Fetches 3 relevant news headlines using the **Marketaux API**
- Assigns a risk level (`Low`, `Medium`, `High`) to each
- Converts that into a **normalized inverse score** (0–100 scale)
- Returns a verdict: **Safe**, **Watch**, or **Risky**

> ⚠️ This module uses the **free tier of the [Marketaux API](https://www.marketaux.com/)**, which allows up to **250 requests per day**.  
> If the quota is exhausted, the system gracefully switches to fallback mode and displays:  
> `"Risk analysis unavailable. Try again tomorrow."`

---

## 🧠 How Sentiment Analysis Works

- Pulls top 10 headlines using **Google News RSS**
- Filters based on selected analysis basis (Quarterly or Annual)
- Scores each headline using **VADER** and **TextBlob**
- Outputs a **sentiment score (0–10)** and top 5 labeled headlines
- Label: 🟢 Positive / 🟡 Neutral / 🔴 Negative

---

## 🔍 Tech Stack

- **Frontend/UI:** Streamlit
- **Backend Logic:** Python
- **Data APIs:** 
  - `yFinance` for stock & financial data
  - `Google News RSS` for sentiment scoring (free)
  - `Marketaux API` (free tier, 250 req/day) for risk headlines
- **AI/NLP Tools:** VADER, TextBlob
- **PDF/CSV Reports:** FPDF, Pandas
- **AI LLM Integration:** OpenAI (ChatGPT for summaries & routing)
- **Deployment:** Streamlit Cloud

---

## 🤖 Role of AI

AI tools (ChatGPT) were used to:
- Accelerate coding, debugging, and modular refactoring
- Validate investment scoring logic
- Create the AI-driven UI for user interaction

> 💡 The **original idea, scoring frameworks, and full integration** were developed independently.

---

## ⚠️ Data Disclaimer

This project uses **public financial data** from `yfinance` and open news feeds like Google RSS.  
Some values (e.g., FCF, segment-level risk) may not be 100% accurate.

> Architecture is **data-source agnostic** — future versions can integrate paid APIs (e.g., Alpha Vantage, IEX Cloud, RavenPack).

---

## 📈 Future Improvements

- 🔐 User authentication (login & history)
- 📈 Backtesting and historical score tracking
- 🧠 AI explainability for investment verdict
- 🌐 ETF & Mutual Fund coverage
- 📡 Premium news APIs for better risk insights

---

## 🧠 My Learning Outcomes

- Designed multi-factor investment scoring models (TA + FA)
- Built sentiment & risk engines based on real-time headlines
- Integrated LLM-based chatbot to guide investor decisions
- Learned full-stack deployment, fallback logic, and PDF report generation

---

## 👋 About Me

I'm a second-year undergraduate passionate about consulting, finance, AI, and strategic thinking.  
**StockMatrix** was built independently — from research and modeling to full deployment — using a blend of AI tools and strong domain understanding.

---

## 📫 Contact

**Email:** writekushagra12@gmail.com  
**LinkedIn:** [linkedin.com/in/kushagra-kb1210](https://www.linkedin.com/in/kushagra-kb1210)

---
