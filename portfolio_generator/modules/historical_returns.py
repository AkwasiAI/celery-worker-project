import requests
from time import sleep
import os
import json

FMP_API_KEY = os.getenv("FMP_API_KEY")

tickers = [
    "HAFNI.OL", "STNG", "TRMD", "FRO", "ECO", "DHT", "INSW", "NAT", "TEN",
    "IMPP", "PSHG", "TORO", "TNK", "PXS", "TOPS", "DSX", "GNK", "GOGL",
    "NMM", "SB", "SBLK", "SHIP", "2020.OL", "HSHP", "EDRY", "JINO.XD",
    "CTRM", "ICON", "GLBS", "CMRE", "DAC", "GSL", "ESEA", "MPCC.OL", "ZIM",
    "SFL", "BWLPGO.XD", "LPG", "CCEC", "GASS", "DLNG", "AGASO.OL", "ALNGO.OL",
    "CLCO", "FLNG", "RIG", "HLX", "PRS.OL", "SPM.MI", "SBMO.VI", "TDW", "RIO",
    "BHP", "VALE", "GLNCY", "ADM", "WLMIY", "BG", "SHEL", "XOM", "CVX", "TTE",
    "WPM", "VALE", "CLF", "ALB", "MOS", "BDRY", "BWET", "^DJI", "^SPX", "^GSPTSE",
    "^MXX", "^BVSP", "^STOXX50E", "UKXDUK.L", "^FCHI", "FTSEMIB.MI", "^OMX", "SMIN.SW",
    "^N225", "^HSI", "000300.SS", "^AXJO", "URTH"
]

def get_historical_prices_fmp(symbol, apikey, days=400):
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}?timeseries={days}&apikey={apikey}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return []
    data = resp.json()
    return data.get('historical', [])

def get_returns(prices, periods=[7,28,365]):
    if not prices or len(prices) < max(periods)+1:
        return {f"{p}_days": None for p in periods}
    results = {}
    latest = prices[0]['close']
    for p in periods:
        if len(prices) > p:
            prev = prices[p]['close']
            results[f"{p}_days"] = (latest / prev - 1) * 100
        else:
            results[f"{p}_days"] = None
    return results

def get_returns_yf(ticker, periods=[7,28,365]):
    import yfinance as yf
    df = yf.download(ticker, period=f"{max(periods)+10}d", interval="1d", progress=False)
    df = df.sort_index(ascending=False)
    closes = df['Close'].tolist()
    if len(closes) < max(periods) + 1:
        return {f"{p}_days": None for p in periods}
    results = {}
    for p in periods:
        try:
            latest = closes[0]
            prev = closes[p]
            results[f"{p}_days"] = (latest / prev - 1) * 100
        except Exception:
            results[f"{p}_days"] = None
    return results

def fetch_all_ticker_returns_combined(tickers = tickers, fmp_api_key = FMP_API_KEY, periods=[7,28,365], sleep_time=1):
    all_results = {}
    for symbol in tickers:
        # 1. Try FMP first
        try:
            prices = get_historical_prices_fmp(symbol, fmp_api_key)
            returns = get_returns(prices, periods)
        except Exception:
            returns = {f"{p}_days": None for p in periods}

        # 2. If FMP failed or is missing all data, try Yahoo Finance
        if all(v is None for v in returns.values()):
            try:
                returns = get_returns_yf(symbol, periods)
            except Exception:
                returns = {f"{p}_days": None for p in periods}

        all_results[symbol] = returns
        sleep(sleep_time)
    return all_results