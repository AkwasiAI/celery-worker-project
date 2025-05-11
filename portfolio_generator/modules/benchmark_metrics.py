import asyncio
import json
from pydantic import BaseModel
from portfolio_generator.prompts_config import BENCHMARK_CALCULATIONS_PROMPT

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

async def calculate_benchmark_metrics(client, portfolio_json, current_date):
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
