# backend/strategic_insights.py
import pandas as pd
from . import fundamental_analysis as fa_mod
from . import technical_analysis as ta_mod
from . import news_risk_analyzer as news_mod
from .data_fetcher import get_ticker_data

# --- NEW: Single Stock Profile Checker ---
def check_single_stock_strategies(ticker: str):
    """
    Analyzes a single stock against all predefined strategies.
    Returns a list of matched strategies and explanatory notes.
    """
    insights = []
    notes = []

    try:
        # Step 1: Fetch all necessary analysis data
        fa_data = fa_mod.analyze_fundamentals(ticker)
        ta_data = ta_mod.analyze_technical_indicators(ticker)
        news_data = news_mod.fetch_news_risk(ticker)
        info = get_ticker_data(ticker).get("info", {})

        if "error" in fa_data or "error" in ta_data or "error" in news_data:
            return ["Analysis failed for one or more modules."], []

        # Step 2: Extract all required metrics
        pe_ratio = fa_data.get("pe_ratio")
        revenue_growth = fa_data.get("revenue_growth")
        ta_score = ta_data.get("ta_score")
        roe = fa_data.get("roe")
        de_ratio = fa_data.get("de_ratio")
        price = info.get("currentPrice")
        sma_200_str = ta_data.get("indicators", {}).get("SMA_200")
        pb_ratio = fa_data.get("pb_ratio")
        news_verdict = news_data.get("verdict")
        free_cash_flow = fa_data.get("free_cash_flow")
        
        # Step 3: Check against each strategy's criteria
        # 1. GARP Strategy
        if all(v is not None for v in [revenue_growth, pe_ratio, ta_score]):
            if revenue_growth > 0.15 and ta_score > 70 and pe_ratio < 40:
                insights.append("✅ GARP (Growth at a Reasonable Price)")
                notes.append("Matches GARP: High revenue growth, strong technicals, and a reasonable P/E ratio.")

        # 2. Fallen Angels
        try: sma_200_val = float(sma_200_str) if sma_200_str != "N/A" else None
        except (ValueError, TypeError): sma_200_val = None
        if all(v is not None for v in [roe, de_ratio, price, sma_200_val]):
            if roe > 20 and de_ratio < 1 and price < sma_200_val:
                insights.append("✅ Fallen Angel (Quality + Value)")
                notes.append("Matches Fallen Angel: Strong fundamentals (high ROE, low debt) but trading below its 200-day SMA.")

        # 3. Value Trap Detector
        if all(v is not None for v in [pb_ratio, pe_ratio, news_verdict]):
             if pe_ratio < 15 and pb_ratio < 1.5 and any(risk in news_verdict for risk in ["High Risk", "Extreme Risk", "Elevated Risk"]):
                 insights.append("⚠️ Potential Value Trap")
                 notes.append("Flagged as a Value Trap: Appears cheap by valuation, but carries significant news-related risk.")

        # 4. Momentum + Quality Combo
        if all(v is not None for v in [roe, free_cash_flow, ta_score]):
            if roe > 15 and free_cash_flow > 0 and ta_score > 75:
                insights.append("✅ Momentum + Quality")
                notes.append("Matches Momentum + Quality: High-quality business (strong ROE, positive FCF) with strong price momentum.")

        if not insights:
            return ["This stock does not strongly match any predefined strategic profiles."], []

        return insights, notes

    except Exception as e:
        return [f"An error occurred during single stock insight generation: {e}"], []


# --- Screening Functions (for DataFrames) ---

def run_garp_strategy(df):
    """Growth at a Reasonable Price (GARP): Revenue Growth > 15%, TA Score > 70, P/E < 40"""
    filtered = df[(df['revenue_growth'] > 0.15) & (df['ta_score'] > 70) & (df['pe_ratio'] < 40)]
    filtered = filtered.copy()
    filtered['insight'] = 'Meets GARP logic (Growth + Reasonable Valuation)'
    return filtered

def run_fallen_angels(df):
    """Fallen Angels: ROE > 20%, Debt-to-Equity < 1, Price < 200-day SMA"""
    filtered = df[(df['roe'] > 20) & (df['de_ratio'] < 1) & (df['price'] < df['sma_200'])]
    filtered = filtered.copy()
    filtered['insight'] = 'Fallen Angel: Strong fundamentals, undervalued technically'
    return filtered

def run_value_trap_filter(df, news_verdicts):
    """Value Trap Detector: P/E < 15, P/B < 1.5, News Risk Verdict in ["Risky", "Watch"]"""
    filtered = df[(df['pe_ratio'] < 15) & (df['pb_ratio'] < 1.5)]
    filtered = filtered.copy()
    filtered['news_verdict'] = filtered['ticker'].map(news_verdicts)
    filtered = filtered[filtered['news_verdict'].isin(['Risky', 'Watch'])]
    filtered['insight'] = 'Flagged as potential value trap (cheap but risky)'
    return filtered

def run_momentum_quality_combo(df):
    """Momentum + Quality: ROE > 15%, Free Cash Flow > 0, TA Score > 75"""
    filtered = df[(df['roe'] > 15) & (df['free_cash_flow'] > 0) & (df['ta_score'] > 75)]
    filtered = filtered.copy()
    filtered['insight'] = 'Momentum + Quality: High quality, strong trend'
    return filtered

def run_low_volatility_anomaly(df, news_verdicts):
    """Low Volatility Anomaly: Volatility < 0.25, FA Score > 60, News Risk Verdict != 'Risky'"""
    filtered = df[(df['volatility'] < 0.25) & (df['fa_score'] > 60)]
    filtered = filtered.copy()
    filtered['news_verdict'] = filtered['ticker'].map(news_verdicts)
    filtered = filtered[filtered['news_verdict'] != 'Risky']
    filtered['insight'] = 'Low Volatility: Stable, solid upside'
    return filtered
