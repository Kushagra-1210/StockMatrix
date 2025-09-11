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

    def run_simulation(self, rebalance_frequency='ME'): # Note: Changed 'M' to 'ME'
        """
        Executes the backtesting simulation.

        Args:
            rebalance_frequency (str): Pandas offset string for rebalancing ('ME' for month-end).
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
                    
                    # --- START OF FIX ---
                    # Handle cases where asof() might return a Series due to duplicate indices
                    if isinstance(start_price, pd.Series):
                        start_price = start_price.iloc[0]
                    if isinstance(end_price, pd.Series):
                        end_price = end_price.iloc[0]
                    # --- END OF FIX ---

                    if start_price is not None and pd.notna(start_price) and start_price > 0:
                        period_return += (end_price / start_price) - 1
                except (KeyError, IndexError, TypeError):
                    continue 
            
            if current_portfolio:
                avg_return = period_return / len(current_portfolio)
                portfolio_value *= (1 + avg_return)

            # --- Calculate Benchmark Performance ---
            try:
                benchmark_start = benchmark_prices.asof(date)
                benchmark_end = benchmark_prices.asof(period_end_date)

                # --- START OF FIX ---
                if isinstance(benchmark_start, pd.Series):
                    benchmark_start = benchmark_start.iloc[0]
                if isinstance(benchmark_end, pd.Series):
                    benchmark_end = benchmark_end.iloc[0]
                # --- END OF FIX ---

                if benchmark_start is not None and pd.notna(benchmark_start) and benchmark_start > 0:
                    benchmark_return = (benchmark_end / benchmark_start) - 1
                    benchmark_value *= (1 + benchmark_return)
            except (KeyError, IndexError, TypeError):
                pass

            self.dates.append(date)
            self.portfolio_history.append(portfolio_value)
            self.benchmark_history.append(benchmark_value)

        logger.info("Backtest simulation finished.")
        return self.get_results()

    def get_results(self):
        """
        Calculates and returns the final results and performance metrics of the backtest.
        """
        if not self.dates or len(self.dates) < 2:
            return {
                "performance_df": pd.DataFrame(),
                "metrics": {}
            }
            
        results_df = pd.DataFrame({
            'Date': self.dates,
            'Strategy': self.portfolio_history,
            'Benchmark': self.benchmark_history
        }).set_index('Date')

        # --- Performance Metrics ---
        total_days = (results_df.index[-1] - results_df.index[0]).days
        years = max(total_days / 365.25, 1/365.25) # Avoid division by zero for short periods

        # Total Return
        total_return_strategy = (results_df['Strategy'].iloc[-1] / results_df['Strategy'].iloc[0]) - 1
        total_return_benchmark = (results_df['Benchmark'].iloc[-1] / results_df['Benchmark'].iloc[0]) - 1
        
        # CAGR
        cagr_strategy = ((results_df['Strategy'].iloc[-1] / results_df['Strategy'].iloc[0]) ** (1/years)) - 1
        cagr_benchmark = ((results_df['Benchmark'].iloc[-1] / results_df['Benchmark'].iloc[0]) ** (1/years)) - 1

        # Alpha (Strategy Total Return - Benchmark Total Return)
        alpha = total_return_strategy - total_return_benchmark

        # Sharpe Ratio (assuming monthly rebalancing and 2% annual risk-free rate)
        strategy_returns = results_df['Strategy'].pct_change().dropna()
        benchmark_returns = results_df['Benchmark'].pct_change().dropna()
        risk_free_rate_annual = 0.02
        
        # Assuming 12 rebalancing periods per year
        periods_per_year = 12 
        
        excess_returns_strategy = strategy_returns - (risk_free_rate_annual / periods_per_year)
        sharpe_strategy = (excess_returns_strategy.mean() / excess_returns_strategy.std()) * np.sqrt(periods_per_year) if excess_returns_strategy.std() != 0 else 0
        
        excess_returns_benchmark = benchmark_returns - (risk_free_rate_annual / periods_per_year)
        sharpe_benchmark = (excess_returns_benchmark.mean() / excess_returns_benchmark.std()) * np.sqrt(periods_per_year) if excess_returns_benchmark.std() != 0 else 0

        metrics = {
            "total_return_strategy_pct": total_return_strategy * 100,
            "total_return_benchmark_pct": total_return_benchmark * 100,
            "cagr_strategy_pct": cagr_strategy * 100,
            "cagr_benchmark_pct": cagr_benchmark * 100,
            "alpha_pct": alpha * 100,
            "sharpe_strategy": sharpe_strategy if pd.notna(sharpe_strategy) else 0,
            "sharpe_benchmark": sharpe_benchmark if pd.notna(sharpe_benchmark) else 0,
            "start_date": self.start_date.strftime('%Y-%m-%d'),
            "end_date": self.end_date.strftime('%Y-%m-%d'),
            "benchmark_ticker": self.benchmark_ticker
        }

        return {
            "performance_df": results_df,
            "metrics": metrics
        }

