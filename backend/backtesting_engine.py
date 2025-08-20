# backend/backtesting_engine.py
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Assuming other modules are in the same backend package
from .historical_data_cache import HistoricalDataCache
from .leaderboard_engine import _process_ticker_for_leaderboard # Use the worker function

logger = logging.getLogger(__name__)

class BacktestingEngine:
    """
    Orchestrates the backtesting process for the StockMatrix strategy.
    """
    def __init__(self, tickers: list, benchmark_ticker: str, start_date: str, end_date: str):
        """
        Initializes the engine with necessary parameters.

        Args:
            tickers (list): List of stock tickers to include in the universe.
            benchmark_ticker (str): The ticker for the market benchmark (e.g., '^NSEI').
            start_date (str): The start date for the backtest in 'YYYY-MM-DD' format.
            end_date (str): The end date for the backtest in 'YYYY-MM-DD' format.
        """
        self.universe = tickers
        self.benchmark_ticker = benchmark_ticker
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.data_cache = HistoricalDataCache(tickers + [benchmark_ticker], start_date, end_date)
        
        # Portfolio tracking
        self.portfolio_history = []
        self.benchmark_history = []
        self.dates = []

    def _get_top_stocks_for_date(self, date):
        """
        Runs the leaderboard logic for a specific point in time.
        """
        # This is a simplified version. A true point-in-time backtest
        # would require passing the historical fundamental data into the analysis functions.
        # For this implementation, we'll use the leaderboard engine which uses the most recent data,
        # acknowledging this as a simplification.
        
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_ticker = {executor.submit(_process_ticker_for_leaderboard, ticker): ticker for ticker in self.universe}
            for future in as_completed(future_to_ticker):
                result = future.result()
                if result:
                    results.append(result)
        
        if not results:
            return []

        df = pd.DataFrame(results)
        df_sorted = df.sort_values("Final Score", ascending=False).reset_index(drop=True)
        return df_sorted.head(10)['Ticker'].tolist()

    def run_simulation(self, rebalance_frequency='M'):
        """
        Executes the backtesting simulation.

        Args:
            rebalance_frequency (str): Pandas offset string for rebalancing ('M' for month-end).
        """
        logger.info("Starting backtest simulation...")
        self.data_cache.load_all_data()
        
        rebalance_dates = pd.date_range(self.start_date, self.end_date, freq=rebalance_frequency)
        
        current_portfolio = []
        portfolio_value = 100000  # Start with $100,000
        benchmark_value = 100000
        
        benchmark_prices = self.data_cache.get_price_data(self.benchmark_ticker)
        if benchmark_prices is None or benchmark_prices.empty:
            raise ValueError("Benchmark data could not be loaded.")
            
        initial_benchmark_price = benchmark_prices.iloc[0]

        for i, date in enumerate(rebalance_dates):
            logger.info(f"Rebalancing for {date.date()}...")
            
            # --- Rebalance Portfolio ---
            top_stocks = self._get_top_stocks_for_date(date)
            
            if not top_stocks:
                logger.warning(f"No top stocks found for {date.date()}. Holding previous portfolio.")
            else:
                current_portfolio = top_stocks

            # --- Calculate Performance for the Period ---
            if i + 1 < len(rebalance_dates):
                period_end_date = rebalance_dates[i+1]
            else:
                period_end_date = self.end_date

            period_return = 0
            for stock in current_portfolio:
                price_data = self.data_cache.get_price_data(stock)
                if price_data is None: continue
                
                try:
                    start_price = price_data.asof(date)
                    end_price = price_data.asof(period_end_date)
                    period_return += (end_price / start_price) - 1
                except (KeyError, IndexError):
                    continue # Skip if data is missing for this period
            
            # Equal-weighted portfolio return
            if current_portfolio:
                avg_return = period_return / len(current_portfolio)
                portfolio_value *= (1 + avg_return)

            # --- Calculate Benchmark Performance ---
            try:
                benchmark_start = benchmark_prices.asof(date)
                benchmark_end = benchmark_prices.asof(period_end_date)
                benchmark_return = (benchmark_end / benchmark_start) - 1
                benchmark_value *= (1 + benchmark_return)
            except (KeyError, IndexError):
                # If benchmark data is missing, hold value
                pass

            self.dates.append(date)
            self.portfolio_history.append(portfolio_value)
            self.benchmark_history.append(benchmark_value)

        logger.info("Backtest simulation finished.")
        return self.get_results()

    def get_results(self):
        """
        Returns the results of the backtest.
        """
        results_df = pd.DataFrame({
            'Date': self.dates,
            'Strategy': self.portfolio_history,
            'Benchmark': self.benchmark_history
        }).set_index('Date')

        # --- Performance Metrics ---
        total_return_strategy = (results_df['Strategy'].iloc[-1] / results_df['Strategy'].iloc[0]) - 1
        total_return_benchmark = (results_df['Benchmark'].iloc[-1] / results_df['Benchmark'].iloc[0]) - 1

        return {
            "performance_df": results_df,
            "total_return_strategy_pct": total_return_strategy * 100,
            "total_return_benchmark_pct": total_return_benchmark * 100,
        }
