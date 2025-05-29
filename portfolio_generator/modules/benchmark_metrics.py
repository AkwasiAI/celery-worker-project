import asyncio
import json
from pydantic import BaseModel
from portfolio_generator.prompts_config import BENCHMARK_CALCULATIONS_PROMPT
import json
import pandas as pd
import numpy as np
import yfinance as yf

class Correlation(BaseModel):
    SP500: float
    MSCI: float

class BenchmarkMetrics(BaseModel):
    daily_return: float
    month_to_date_return: float
    year_to_date_return: float
    sharpe_ratio: float
    annualised_std: float
    correlation: Correlation

async def calculate_benchmark_metrics_with_llm(client, portfolio_json, current_date):
    print("DEBUG: Starting calculate_benchmark_metrics")
    try:
        print("DEBUG: Building user prompt...")
        user_prompt = BENCHMARK_CALCULATIONS_PROMPT + f"\nCurrent date: {current_date}\n\nPortfolio Weights JSON:\n{portfolio_json}"
        strict_system_prompt = (
            "You are a world-class investment analyst with access to real-time market data via web search. "
            "Use the web search tool to fetch up-to-date market metrics. "
            "Respond with only the pure JSON object matching the requested structure, without any extra text."
        )
        tools = [{"type": "web_search_preview"}]
        print("DEBUG: Sending API request via Responses API...")
        response = await asyncio.to_thread(
            client.responses.parse,
            model="gpt-4.1",
            input=[
                {"role": "system", "content": strict_system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            tools=tools,
            temperature=0.1,
            text_format=BenchmarkMetrics
        )
        print("DEBUG: Received parse response")
        print("DEBUG: Raw parse output:", response.output)
        metrics_obj = response.output_parsed
        print("DEBUG: Parsed metrics_obj:", metrics_obj)
        print("DEBUG: Returning JSON string...")
        return metrics_obj.model_dump_json(indent=2)
    except Exception as e:
        print(f"ERROR: calculate_benchmark_metrics failed: {e}")
        return json.dumps({})
    

async def calculate_benchmark_metrics(noclient, portfolio_json, current_date):
    try:
        print("Received portfolio input")
        if isinstance(portfolio_json, str):
            portfolio_json = json.loads(portfolio_json)

        assets = portfolio_json['portfolio']['assets']
        print(f"Found {len(assets)} assets")

        # Include both LONG and SHORT positions
        included_assets = [a for a in assets if a['position'] in ['LONG', 'SHORT']]
        print(f"{len(included_assets)} tradable positions retained (LONG + SHORT)")

        # Build ticker -> signed weight mapping
        raw_weights = {
            a['ticker']: a['weight'] if a['position'] == 'LONG' else -a['weight']
            for a in included_assets
        }

        # Validate tickers (using yf.Ticker.info as a basic test)
        valid_weights = {}
        for ticker in raw_weights:
            try:
                yf.Ticker(ticker).info  # This will throw for delisted/invalid
                valid_weights[ticker] = raw_weights[ticker]
            except Exception:
                print(f"Skipping invalid/delisted ticker: {ticker}")

        if not valid_weights:
            raise ValueError("No valid tickers found in portfolio.")

        tickers = list(valid_weights.keys())

        # Normalize weights
        weights = [valid_weights[t] for t in tickers]
        total_weight = sum(abs(w) for w in weights)
        if total_weight == 0:
            raise ValueError("Total absolute weight is zero.")
        weights = [w / total_weight for w in weights]

        # Date range
        end_date = pd.to_datetime(current_date)
        start_date = end_date - pd.Timedelta(days=365)

        # Download prices for portfolio tickers and benchmarks
        benchmark_tickers = ['^GSPC', 'URTH']
        all_tickers = tickers + benchmark_tickers
        print(f"Fetching data for: {all_tickers}")

        raw_data = yf.download(all_tickers, start=start_date, end=end_date, auto_adjust=True)
        data = raw_data['Close'] if 'Close' in raw_data else raw_data

        # Remove portfolio tickers with all-NaN data after download
        available_tickers = [t for t in tickers if t in data.columns and not data[t].isnull().all()]
        if not available_tickers:
            raise ValueError("No valid tickers with available price data after download.")

        # Renormalize weights for available tickers
        weights = [valid_weights[t] for t in available_tickers]
        total_weight = sum(abs(w) for w in weights)
        weights = [w / total_weight for w in weights]
        tickers = available_tickers

        # Keep only the available tickers and benchmarks in data
        data = data[tickers + benchmark_tickers].dropna(how='all')

        # Calculate daily returns
        returns = data.pct_change().dropna()

        # After pct_change, ensure we only use days where all portfolio tickers have data
        returns = returns.dropna(subset=tickers, how='any')
        if returns.empty:
            raise ValueError("Not enough price data to compute returns.")

        # Resync tickers and weights with returns columns (handles late missing tickers)
        final_tickers = [t for t in tickers if t in returns.columns]
        if not final_tickers:
            raise ValueError("No tickers left with valid returns data.")

        final_weights = [valid_weights[t] for t in final_tickers]
        total_weight = sum(abs(w) for w in final_weights)
        final_weights = [w / total_weight for w in final_weights]

        # Compute portfolio returns
        portfolio_returns = (returns[final_tickers] * final_weights).sum(axis=1)
        if portfolio_returns.empty:
            raise ValueError("No valid portfolio returns could be calculated.")

        # Benchmark returns
        sp500_returns = returns['^GSPC'] if '^GSPC' in returns.columns else pd.Series(index=portfolio_returns.index, data=np.nan)
        msci_returns = returns['URTH'] if 'URTH' in returns.columns else pd.Series(index=portfolio_returns.index, data=np.nan)

        def compound_return(series):
            return (series + 1).prod() - 1 if not series.empty else float('nan')

        # Accurate MTD & YTD filters (year + month match)
        mtd_returns = portfolio_returns[
            (portfolio_returns.index.month == end_date.month) &
            (portfolio_returns.index.year == end_date.year)
        ]
        ytd_returns = portfolio_returns[
            portfolio_returns.index.year == end_date.year
        ]

        # Metrics
        daily_return = portfolio_returns.iloc[-1] if not portfolio_returns.empty else float('nan')
        month_to_date_return = compound_return(mtd_returns)
        year_to_date_return = compound_return(ytd_returns)

        risk_free_rate = 0.03  # 3% annual hardcoded
        sharpe_ratio = (
            ((portfolio_returns.mean() - risk_free_rate / 252) / portfolio_returns.std()) * np.sqrt(252)
            if portfolio_returns.std() != 0 else float('nan')
        )
        annualised_std = portfolio_returns.std() * np.sqrt(252)
        correlation = {
            "S&P 500": round(float(portfolio_returns.corr(sp500_returns)), 2) if not sp500_returns.isnull().all() else None,
            "MSCI": round(float(portfolio_returns.corr(msci_returns)), 2) if not msci_returns.isnull().all() else None
        }

        metrics = {
            "daily_return": round(float(daily_return), 4) if not np.isnan(daily_return) else None,
            "month_to_date_return": round(float(month_to_date_return), 4) if not np.isnan(month_to_date_return) else None,
            "year_to_date_return": round(float(year_to_date_return), 4) if not np.isnan(year_to_date_return) else None,
            "sharpe_ratio": round(float(sharpe_ratio), 2) if not np.isnan(sharpe_ratio) else None,
            "annualised_std": round(float(annualised_std), 4) if not np.isnan(annualised_std) else None,
            "correlation": correlation
        }

        print("Benchmark metrics successfully calculated")
        return json.dumps(metrics, indent=2)

    except Exception as e:
        print("ERROR: Failed to calculate benchmark metrics:", e)
        return json.dumps({})