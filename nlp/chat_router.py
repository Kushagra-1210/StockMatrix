# nlp/chat_router.py
import re

def handle_chat_command(user_input: str) -> tuple[str, str | None]:
    """
    Interprets a user's text command to determine their intent and extract a stock ticker.
    This function does NOT call any backend modules. Its only job is to parse text.

    Args:
        user_input: The raw text entered by the user.

    Returns:
        A tuple containing:
        - command (str): The identified command (e.g., "run_analysis", "report", "screener").
        - ticker (str | None): The extracted stock ticker symbol, if any.
    """
    text = user_input.lower().strip()
    
    # --- Command Recognition using keywords ---
    # This block maps various user inputs to standardized internal commands.
    if any(cmd in text for cmd in ["run analysis", "analyze", "ra"]):
        command = "run_analysis"
    elif any(cmd in text for cmd in ["generate report", "report", "gr"]):
        command = "report"
    elif any(cmd in text for cmd in ["screener", "find stocks", "insight generation", "ig"]):
        # Consolidating "insight generation" into "screener" for simplicity.
        # You can show both screener and leaderboard buttons when this command is returned.
        command = "insight_generation"
    elif any(cmd in text for cmd in ["leaderboard", "top stocks"]):
        command = "stock_leaderboard"
    else:
        command = "unknown"

    # --- Ticker Extraction using Regular Expressions ---
    # This regex looks for a capitalized word of 1-5 letters,
    # which can optionally be preceded by a '$' sign (e.g., "$AAPL" or "MSFT").
    ticker_match = re.search(r'\$?([A-Z]{1,5})\b', user_input.upper())
    ticker = ticker_match.group(1) if ticker_match else None
    
    return command, ticker