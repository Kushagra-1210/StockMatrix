# strategic_insights.py
"""
Module: strategic_insights.py
Provides research-backed investment strategies for stock screening and insights.
"""
import pandas as pd

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
