# Routing logic for StockMatrix main UI
def get_view(mode):
    """Routing logic for StockMatrix main UI"""
    if mode == "screener":
        from .screener import show_screener
        return show_screener
    elif mode == "stock_leaderboard":
        from .leaderboard import show_leaderboard
        return show_leaderboard
    elif mode == "run_analysis":
        from .run_analysis import show_run_analysis
        return show_run_analysis
    elif mode == "report":
        from .report import show_report
        return show_report
    elif mode == "onboarding":
        from .onboarding import show_onboarding
        return show_onboarding
    elif mode == "strategic_insights":
        from .strategic_insights import show_strategic_insights
        return show_strategic_insights
    elif mode == "backtesting": # New route
        from .backtesting import show_backtesting
        return show_backtesting
    else:
        from .watchlist import show_watchlist
        return show_watchlist
