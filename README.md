# 📊 StockMatrix – Global Equity Intelligence Platform (In Progress)

**Author:** Kushagra Bansal  
**GitHub Repository:** [StockMatrix](https://github.com/Kushagra-1210/StockMatrix)  
**Live Demo:** [Streamlit App](https://stockmatrix-kb.streamlit.app/)  

---

## 🌍 Overview  
StockMatrix is a **global equity intelligence platform** designed to address the **fragmentation in investment research**.  
It unifies **fundamentals, technicals, sentiment, and geopolitical risk** into a **standardized multi-factor scoring model** across multiple exchanges:  

- **NYSE** (US)  
- **NSE** (India)  
- **LSE** (UK)  
- **TSE** (Japan)  
- **HKEX** (Hong Kong)  

The project is currently **in progress (Proxen)** and aims to evolve into a **scalable decision-support system** for analysts, consultants, and independent investors.

---

## 🔑 Key Features (Implemented)
- ✅ **Multi-Factor Scoring Framework** – combines 20+ metrics from fundamentals, technicals, sentiment, and risk.  
- ✅ **Equity Screeners & Leaderboards** – rank companies by performance across markets.  
- ✅ **Chatbot-First Interface** – query stocks conversationally and receive structured reports.  
- ✅ **PDF Report Generator** – exportable investment insights for documentation and sharing.  
- ✅ **AI-Accelerated Development** – leveraged ChatGPT & GitHub Copilot for rapid coding, prototyping, and algorithm refinement.  

---

## 🚀 Upcoming Features (Roadmap – Proxen)
- 🔄 **Backtesting Engine** – simulate investment strategies and evaluate performance vs benchmarks.  
- 🔄 **3D Market Visualizer** – interactive visualization of global market dynamics.  
- 🔄 **Strategy Insight Dashboard** – structured, consultant-style view of investment strategy effectiveness.  

---

## 🏗️ System Architecture
StockMatrix is built with a **modular design** to ensure scalability and extensibility:  

1. **Data Fetching Layer**  
   - APIs: Yahoo Finance, FMP (Financial Modeling Prep), Marketaux (news & sentiment)  
   - Historical Data Caching for performance  

2. **Analysis Engine**  
   - Fundamental Analysis (Altman Z, Beneish M, Piotroski F-score, ratios)  
   - Technical Analysis (RSI, MACD, moving averages)  
   - Sentiment & Geopolitical Risk Processing  

3. **Backtesting & Strategy Module**  
   - Evaluate custom strategies on historical data  
   - Generate comparison reports and leaderboards  

4. **User Interface**  
   - Streamlit app for dashboards and reports  
   - AI-powered chat assistant for queries  

---

## ⚙️ Tech Stack
- **Programming Language:** Python  
- **Frontend / UI:** Streamlit  
- **Backend:** Pandas, NumPy, SQLAlchemy (for database), REST APIs  
- **Data Sources:** Yahoo Finance, FMP API, Marketaux API  
- **AI Tools:** ChatGPT, GitHub Copilot (development acceleration)  
- **Visualization:** Matplotlib, Plotly (future: 3D visualizer)  

---

## 🧪 Testing
- Unit tests available in `/tests` using `pytest`.  
- Tests mock API responses to validate functionality without relying on external services.  
- Example: Fundamental analysis test for AAPL with FMP data.  

Run tests locally:  
```bash
pytest -q
