import os
import json
import asyncio
import pytest
from openai import OpenAI
from portfolio_generator.modules.benchmark_metrics import calculate_benchmark_metrics

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
def test_calculate_benchmark_metrics_integration():
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    dummy_portfolio = {
        "data": {
            "report_date": "2025-05-10",
            "assets": [
                {"ticker": "SPY", "weight": 0.5},
                {"ticker": "AGG", "weight": 0.5}
            ]
        }
    }
    portfolio_json = json.dumps(dummy_portfolio)
    current_date = "2025-05-10"
    metrics_json = asyncio.run(calculate_benchmark_metrics(client, portfolio_json, current_date))
    metrics = json.loads(metrics_json)
    assert isinstance(metrics, dict)
    for key in [
        "daily_return",
        "month_to_date_return",
        "year_to_date_return",
        "sharpe_ratio",
        "annualised_std",
        "correlation"
    ]:
        assert key in metrics
    corr = metrics["correlation"]
    assert isinstance(corr, dict)
    assert "SP500" in corr
    assert "MSCI" in corr
    # Check numeric types
    assert isinstance(metrics["daily_return"], (float, int))
    assert isinstance(metrics["month_to_date_return"], (float, int))
    assert isinstance(metrics["year_to_date_return"], (float, int))
    assert isinstance(metrics["sharpe_ratio"], (float, int))
    assert isinstance(metrics["annualised_std"], (float, int))
