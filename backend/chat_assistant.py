def get_chat_response(
    stock_info,
    technical,
    fundamental,
    sentiment,
    news_risk,
    final_score,
    final_verdict,
    follow_up,
    chat_history=None
) -> str:
    if chat_history is None:
        chat_history = []
    question = (follow_up or "").lower()

    # Broad keywords indicating it's a stock analysis question
    keywords = [
        "verdict", "score", "why", "reason",
        "technical", "fundamental", "sentiment", "news", "risk",
        stock_info.get("ticker", "").lower() if stock_info else ""
    ]

    if any(keyword in question for keyword in keywords):
        # Final verdict explanation
        if "final verdict" in question or "verdict" in question:
            return (
                f"The final verdict is **{final_verdict}** based on combined analysis:\n"
                f"- Fundamental score: {fundamental.get('fa_score', 'N/A') if fundamental else 'N/A'}\n"
                f"- Technical score: {technical.get('ta_score', 'N/A') if technical else 'N/A'}\n"
                f"- Sentiment score: {sentiment.get('score', 'N/A') if sentiment else 'N/A'} (out of 10)\n"
                f"- News & Risk score: {news_risk.get('risk_score', 'N/A') if news_risk else 'N/A'}\n"
                "These scores are weighted and combined to form the investment decision."
            )

        # Technical-related questions
        if any(term in question for term in ["technical", "rsi", "sma", "ema", "ta score", "ta"]):
            return (
                f"📊 **Technical Analysis for {stock_info.get('ticker', 'N/A')}**:\n"
                f"- RSI (14): {technical.get('rsi', 'N/A') if technical else 'N/A'}\n"
                f"- SMA-20: {technical.get('sma_20', 'N/A') if technical else 'N/A'}\n"
                f"- EMA-20: {technical.get('ema_20', 'N/A') if technical else 'N/A'}\n"
                f"- TA Score: {technical.get('ta_score', 'N/A') if technical else 'N/A'} / 100\n"
                f"- Verdict: **{technical.get('verdict', 'N/A')}**"
            )

        # Fundamental-related questions
        if any(term in question for term in ["fundamental", "pe", "roe", "eps", "fcf", "de ratio", "fa score", "fa"]):
            return (
                f"📈 **Fundamental Analysis for {stock_info.get('ticker', 'N/A')}**:\n"
                f"- Market Cap: {fundamental.get('market_cap', 'N/A') if fundamental else 'N/A'}\n"
                f"- EPS: {fundamental.get('eps', 'N/A') if fundamental else 'N/A'}\n"
                f"- ROE: {fundamental.get('roe', 'N/A') if fundamental else 'N/A'}%\n"
                f"- PE Ratio: {fundamental.get('pe_ratio', 'N/A') if fundamental else 'N/A'}\n"
                f"- Debt-to-Equity: {fundamental.get('de_ratio', 'N/A') if fundamental else 'N/A'}\n"
                f"- Free Cash Flow: {fundamental.get('fcf', 'N/A') if fundamental else 'N/A'}\n"
                f"- FA Score: {fundamental.get('fa_score', 'N/A') if fundamental else 'N/A'} / 100\n"
                f"- Verdict: **{fundamental.get('verdict', 'N/A')}**"
            )

        # Sentiment-related questions
        if any(term in question for term in ["sentiment", "emotion", "mood"]):
            return (
                f"💬 **Sentiment Analysis for {stock_info.get('ticker', 'N/A')}**:\n"
                f"- Sentiment Score: {sentiment.get('score', 'N/A')} / 10\n"
                f"- Label: **{sentiment.get('label', 'N/A')}**"
            )

        # News/Risk-related questions
        if any(term in question for term in ["news", "risk", "headline", "geopolitical"]):
            return (
                f"🛡️ **News & Geopolitical Risk for {stock_info.get('ticker', 'N/A')}**:\n"
                f"- Risk Score: {news_risk.get('risk_score', 'N/A')} / 100\n"
                f"- Verdict: **{news_risk.get('verdict', 'N/A')}**"
            )

        # Catch-all for related but vague questions
        return (
            "I can help explain the technical, fundamental, sentiment, or news analysis for this stock.\n"
            "Try asking specific questions like:\n"
            "- Why is the RSI so high?\n"
            "- What is the PE ratio?\n"
            "- Explain the sentiment score.\n"
            "- Why is the final verdict 'Hold'?"
        )

    # If unrelated
    return (
        "❗ Sorry, I can only answer questions related to the stock analysis you requested.\n"
        "Please ask about the technical, fundamental, sentiment, or news risk analysis of the selected stock."
    )
