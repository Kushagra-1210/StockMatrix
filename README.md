# 📈 StockMatrix — AI-Powered Global Stock Analysis Platform

**StockMatrix** is a real-time, AI-powered web application that empowers users to evaluate global stocks through a unified lens of **Fundamental**, **Technical**, **Sentiment**, and **News-Based Risk Analysis** — all navigable via a conversational **AI chatbot interface**.

🔗 **Live App:** [stockmatrix-kb.streamlit.app](https://stockmatrix-kb.streamlit.app)

---

## 💡 The Problem It Solves

Retail investors often struggle to make informed decisions because:

- 🔍 Data is fragmented across platforms (charts, financials, news, etc.)
- ❌ No unified or structured scoring framework
- 📰 Market sentiment and news risk often ignored
- ⚙️ Most tools are too complex for casual investors

**StockMatrix** solves these by integrating multiple layers of analysis into one AI-powered, easy-to-use platform.

---

## 🚀 Key Features

| Feature | Description |
|--------|-------------|
| 🧠 Fundamental Analysis | ✅ 10-factor weighted scoring model |
| 📉 Technical Analysis | ✅ 10-factor weighted trend-based model |
| 💬 Sentiment Analysis | ✅ Scores real-time headlines using VADER + TextBlob |
| 📰 News Risk Analyzer | ✅ Sector-aware scoring using Marketaux API |
| 🏆 Stock Leaderboard | ✅ Top 5 stocks ranked by 6 strategy categories |
| 📊 Screener Engine | ✅ Filter stocks by FA, TA, Volatility |
| 🔄 Quarterly/Annual Toggle | ✅ Dynamically adjusts all metrics |
| 🗣️ AI Chatbot Interface | ✅ Guides users + handles follow-ups |
| 📁 Report Generator | ✅ Download PDF/CSV reports |
| 🧠 Headline-Based Insight | ✅ Displays labeled news sentiment & risk headlines |

---

## ⚙️ How It Works

1. **Choose a stock** from NSE, NYSE, LSE, HKEX, or TSE
2. **Select analysis basis**: Quarterly or Annual
3. **Get a breakdown of**:
   - 📉 Technical trends (RSI, EMA, SMA, etc.)
   - 📊 Financial strength (ROE, PE, EPS, FCF, etc.)
   - 💬 News sentiment score (via live headlines)
   - 📰 Sector-aware risk score (via API)

4. **Explore outputs**:
   - 🎯 Investment score with AI-generated verdict
   - 📊 Screener and leaderboard views
   - 📥 Downloadable reports (PDF + CSV)

---

## 🏆 Stock Leaderboard

Ranks **Top 5 stocks** across **6 strategy categories**:

- 💰 **Strong Buys** – High combined FA + TA score
- 📉 **Undervalued** – Low PE with strong fundamentals
- 📈 **Bullish** – Strong technical indicators
- 🛡️ **Low Risk** – Low volatility + positive sentiment
- 🔴 **Negative Sentiment** – Lowest sentiment score from real headlines
- ⚡ **High Volatility** – Large recent price swings

---

## 🧠 News Risk Analyzer

- Auto-classifies stock into a sector
- Fetches 3 live headlines using the Marketaux API
- Assigns risk level: Low, Medium, or High
- Converts into a normalized 0–100 inverse score
- Returns final verdict: ✅ Safe | ⚠️ Watch | ❌ Risky

> ⚠️ *Limited to 250 API requests/day (free plan). On limit breach, fallback message appears.*

---

## 💬 Sentiment Analysis Engine

- Pulls top 10 headlines from Google News RSS
- Filters based on Quarterly or Annual context
- Scores each headline using:
  - VADER (lexicon-based)
  - TextBlob (polarity-based)
- Returns:
  - Score (0–10)
  - Top 5 headlines with label:
    - 🟢 Positive
    - 🟡 Neutral
    - 🔴 Negative

---

## 🛠️ Tech Stack

- **Frontend:** Streamlit
- **Backend:** Python
- **Data APIs:**
  - `yFinance` — stock prices and financials
  - `Google News RSS` — for sentiment headlines
  - `Marketaux` — for news-based risk headlines
- **AI/NLP:** VADER, TextBlob, OpenAI GPT
- **Reports:** FPDF, Pandas
- **Deployment:** Streamlit Cloud

---

## 🤖 Role of AI in StockMatrix

- 🧠 Built and refined scoring logic
- 🗣️ Powering the chatbot UI and routing
- 📋 Generates human-readable insights
- 💡 Used for development acceleration and QA

---

## ⚠️ Data Disclaimer

This project uses public data sources such as `yFinance`, Google News RSS, and the free tier of the Marketaux API.

- Financial data may contain missing or delayed values (e.g., Free Cash Flow, segment earnings).
- News sentiment and risk analysis depend on real-time headlines and may vary based on headline availability and context.
- The **Marketaux API** is limited to **250 requests/day**. When the limit is exceeded, the app displays:
  > *“Risk analysis unavailable. Try again tomorrow.”*

The platform is **data-source agnostic** — future versions may integrate premium APIs (e.g., Alpha Vantage, IEX Cloud, RavenPack) for higher accuracy and reliability.

---

## 🔮 Future Improvements

- 🔐 User login + analysis history
- 📈 Backtesting + historical scoring trends
- 🧠 Explainable AI for verdicts
- 🌍 ETF and Mutual Fund integration
- 📰 Premium API integrations for deeper risk analysis

---

## 🧠 What I Learned

- Designed FA/TA scoring models and applied them in real-time
- Engineered sentiment + risk pipelines using live news
- Built an AI-guided user experience (UX)
- Mastered Streamlit deployment, caching, and report generation

---

## 👋 About Me

I’m a second-year undergraduate passionate about **consulting**, **finance**, **AI**, and **strategic system design**.

**StockMatrix** was built independently — from research and modeling to full deployment — using a hands-on, interdisciplinary approach.

---

## 📫 Contact

- 📧 Email: [writekushagra12@gmail.com](mailto:writekushagra12@gmail.com)
- 🔗 LinkedIn: [linkedin.com/in/kushagra-kb1210](https://linkedin.com/in/kushagra-kb1210)
