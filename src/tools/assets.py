from typing import Literal
from pydantic import BaseModel
from agents import RunContextWrapper, function_tool
from src.agent.context import Context
from src.api.indicators import IndicatorLiteral
from src.tools import load_prompt


@function_tool
def fetch_historical_price_data(
    ctx: RunContextWrapper[Context],
    ticker_symbol: str,
    interval: Literal["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "4h", "1d", "5d", "1wk", "1mo", "3mo"],
    outputsize: int = 20,
    start_date: str = None, 
    end_date: str = None,
    ):
    """
    Retrieves historical OHLCV (Open, High, Low, Close, Volume) price data for a given ticker symbol.
    Ideal for analyzing price trends, patterns, and historical performance purely based on price action.
    Returns a time series of price points with timestamps.

    Args:
        ticker_symbol (required): Stock ticker or crypto symbol (e.g., "AAPL", "BTC-USD").
        interval (required): Time interval between data points. Options: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 4h, 1d, 5d, 1wk, 1mo, 3mo.
        outputsize (optional): Number of data points to retrieve (default: 20).
        start_date (optional): Start date in YYYY-MM-DD format (e.g., "2024-01-01"). Overrides outputsize if provided.
        end_date (optional): End date in YYYY-MM-DD format (e.g., "2024-12-31"). Defaults to today if not provided.
        return_type (optional): Format to return data in. Options: "raw" for raw data (default), "graph" for a price chart image.
    """
    success, data = ctx.context.yfinance_api.time_series(
        symbol=ticker_symbol, 
        interval=interval, 
        outputsize=outputsize, 
        start_date=start_date, 
        end_date=end_date
    )
    if success:
        return data
    else:
        return {"error": data}

@function_tool
def get_current_market_quote(
    ctx: RunContextWrapper[Context],
    ticker_symbol: list[str],
    interval: Literal["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "4h", "1d", "5d", "1wk", "1mo", "3mo"],
    rolling_period_hours: int = 24,
    ):
    """
    Retrieves a real-time snapshot of current market data for one or more ticker symbols.
    Returns key metrics including: current price, open/high/low/close, volume, average volume,
    price change (absolute and percent), previous close, 52-week high/low range, extended hours
    pricing, exchange info, and currency. Use this for quick market overviews or current state checks.

    Args:
        ticker_symbol (required): List of ticker symbols (e.g., ["AAPL"] for single or ["AAPL", "MSFT", "GOOGL"] for multiple).
        interval (required): Time interval for quote data. Options: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 4h, 1d, 5d, 1wk, 1mo, 3mo.
        rolling_period_hours (optional): Time window in hours to calculate rolling price change (default: 24).
    """
    results = {}
    for symbol in ticker_symbol:
        success, data = ctx.context.yfinance_api.quote(
            symbol=symbol, 
            interval=interval, 
            rolling_period=rolling_period_hours
        )
        results[symbol] = data if success else {"error": data}
    
    return results

@function_tool
async def find_screeners(
    ctx: RunContextWrapper[Context],
    search_query: list[str],
    ):
    """
    Finds available screeners using natural language search.
    Returns a list of screener names and descriptions that can then be used with execute_screener.
    
    Args:
        search_query (required): List of search queries (e.g., ["tech gainers"] for single or ["tech gainers", "crypto stats", "dividend stocks"] for multiple).
    """
    # Get available screeners (needed for all queries)
    success, available_screeners = ctx.context.yfinance_api.available_screeners()
    if not success:
        return {"error": available_screeners}
    
    class ScreenerMatch(BaseModel):
        key: str
        relevance_score: float  # 0.0 to 1.0

    class ScreenerResponse(BaseModel):
        matches: list[ScreenerMatch]

    available_screeners_str = "\n".join([f"{screener['name']}: {screener['description']}" for screener in available_screeners])
    system_prompt = load_prompt("find_screeners.md").format(available_screeners=available_screeners_str)

    results = {}
    for query in search_query:
        try:
            completion = await ctx.context.client.chat.completions.parse(
                model=ctx.context.screener_finder_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                response_format=ScreenerResponse
            )   
            matches = completion.choices[0].message.parsed.matches
            screener_map = {s["name"]: s for s in available_screeners}
            relevant_screeners = [
                {**screener_map[match.key], "relevance_score": match.relevance_score} 
                for match in matches 
                if match.key in screener_map
            ]
            results[query] = relevant_screeners
        except Exception as e:
            results[query] = {"error": f"Failed to search for screeners: {str(e)}"}
    
    return results
    
@function_tool
def execute_screener(
    ctx: RunContextWrapper[Context],
    screener_name: list[str],
    outputsize: int = 10,
    ):
    """
    Executes one or more screeners and returns the ranked results. Use find_screeners first to find valid screener names.
    Returns a ranked list of symbols matching the screener criteria for each screener.

    Args:
        screener_name (required): List of screener names to execute (e.g., ["day_gainers"] for single or ["day_gainers", "most_actives"] for multiple).
        outputsize (optional): Number of results to return per screener (default: 10).
    """
    KEEP_FIELDS = [
        # Identification
        "rank",
        "symbol", 
        "shortName",  # or "longName" - keep one
        "exchange",
        
        # Current Price Data
        "regularMarketPrice",
        "regularMarketChange",
        "regularMarketChangePercent",
        "regularMarketVolume",
        "regularMarketPreviousClose",
        "regularMarketDayHigh",
        "regularMarketDayLow",
        "preMarketPrice",
        "preMarketChangePercent",
        
        # Market Data
        "marketCap",
        "marketState",
        
        # 52-Week Range
        "fiftyTwoWeekLow",
        "fiftyTwoWeekHigh",
        "fiftyTwoWeekChangePercent",
        
        # Valuation Metrics
        "trailingPE",
        "forwardPE",
        "priceToBook",
        "epsTrailingTwelveMonths",
        "epsForward",
        
        # Volume & Averages
        "averageDailyVolume3Month",
        "fiftyDayAverage",
        "twoHundredDayAverage",
        
        # Analyst Rating
        "averageAnalystRating",

        # Earnings
        "earningsTimestamp",
        "isEarningsDateEstimate",

        # Dividends (if analyzing dividend stocks)
        "dividendRate",
        "dividendYield",
        "trailingAnnualDividendYield",
    ]

    results = {}
    for screener in screener_name:
        success, data = ctx.context.yfinance_api.screener(
            screener_name=screener,
            outputsize=outputsize
        )
        if success:
            # Filter to keep only relevant fields
            filtered_values = [
                {k: v for k, v in record.items() if k in KEEP_FIELDS}
                for record in data.get("values", [])
            ]
            data["values"] = filtered_values
            results[screener] = data
        else:
            results[screener] = {"error": data}
    
    return results

@function_tool
def search_for_symbols(
    ctx: RunContextWrapper[Context],
    search_query: list[str], 
    outputsize: int = 10,
    ):
    """
    Searches for ticker symbols by matching against the ticker itself using similarity scoring.
    Use when you have a guessed ticker symbol and want to find the correct or similar tickers.
    Returns matching symbols with basic info (name, exchange, type) sorted by similarity.

    Args:
        search_query (required): List of guessed ticker symbols (e.g., ["AAPL"] for single or ["AAPL", "BTC-USD", "TSLA"] for multiple).
        outputsize (optional): Maximum number of results to return per query, 1-50 (default: 10).
    """
    if outputsize > 50 or outputsize < 1:
        return {"error": f"outputsize must be between 1 and 50, got {outputsize}"}
    
    results = {}
    for query in search_query:
        success, data = ctx.context.alpaca_api.symbol_search(query=query, outputsize=outputsize)
        if success:
            results[query] = data
        else:
            results[query] = {"error": data}
    
    return results

@function_tool
def get_company_profile(
    ctx: RunContextWrapper[Context],
    ticker_symbol: list[str],
    ):
    """
    Retrieves comprehensive company/asset information for fundamental research.
    Returns: business description, sector, industry, headquarters, executive team, market cap,
    P/E ratios, dividend info, 52-week performance, analyst ratings, revenue, margins, and more.
    Use to understand what a company does or gather fundamentals for investment decisions.

    Args:
        ticker_symbol (required): List of ticker symbols (e.g., ["AAPL"] for single or ["AAPL", "MSFT", "GOOGL"] for multiple).
    """
    KEEP_FIELDS = [
        # Identification
        "symbol", "shortName", "longName", "sector", "industry",
        "exchange", "currency", "quoteType",
        
        # Business info
        "longBusinessSummary", "website", "fullTimeEmployees",
        
        # Current pricing
        "currentPrice", "regularMarketPrice", "previousClose",
        "dayHigh", "dayLow", "volume", "averageVolume",
        
        # Valuation metrics
        "marketCap", "enterpriseValue", "trailingPE", "forwardPE",
        "priceToBook", "priceToSalesTrailing12Months", "beta",
        "enterpriseToRevenue", "enterpriseToEbitda",
        
        # Profitability
        "profitMargins", "operatingMargins", "grossMargins",
        "returnOnEquity", "returnOnAssets",
        
        # Financial health
        "totalRevenue", "revenueGrowth", "ebitda", "ebitdaMargins",
        "totalCash", "totalCashPerShare", "totalDebt", "debtToEquity",
        "currentRatio", "quickRatio", "freeCashflow", "operatingCashflow",
        
        # Earnings
        "epsTrailingTwelveMonths", "epsForward", "epsCurrentYear",
        "earningsTimestamp", "isEarningsDateEstimate",
        "mostRecentQuarter", "lastFiscalYearEnd", "nextFiscalYearEnd",
        
        # Analyst ratings
        "recommendationMean", "recommendationKey", "numberOfAnalystOpinions",
        "targetMeanPrice", "targetHighPrice", "targetLowPrice", "targetMedianPrice",
        
        # Performance
        "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "fiftyTwoWeekChangePercent",
        "fiftyDayAverage", "twoHundredDayAverage",
        
        # Dividends
        "dividendRate", "dividendYield", "trailingAnnualDividendRate",
        "trailingAnnualDividendYield", "payoutRatio",
        
        # Short interest
        "sharesShort", "shortRatio", "shortPercentOfFloat",
        
        # Share structure
        "sharesOutstanding", "floatShares",
        "heldPercentInsiders", "heldPercentInstitutions",
    ]
    
    results = {}
    for symbol in ticker_symbol:
        success, data = ctx.context.yfinance_api.profile(symbol=symbol)
        if success:
            # Filter to keep only relevant fields
            filtered_data = {k: v for k, v in data.items() if k in KEEP_FIELDS}
            results[symbol] = filtered_data
        else:
            results[symbol] = {"error": data}
    
    return results

@function_tool
def calculate_technical_indicator(
    ctx: RunContextWrapper[Context],
    ticker_symbol: str,
    indicator: IndicatorLiteral,
    interval: Literal["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "4h", "1d", "5d", "1wk", "1mo", "3mo"] = "1d",
    outputsize: int = 30,
    benchmark_symbol: str | None = None,
    ):
    """
    Computes technical indicators for a given ticker symbol. Supports: EMA (trend), MACD (momentum),
    ADX (trend strength), RSI (overbought/oversold), Stochastic, Bollinger Bands (volatility),
    ATR (volatility), OBV (volume), MFI (money flow), SAR (trend reversal), Typical Price, Beta
    (market correlation), and PPO (momentum). Use for technical analysis and trading signals.

    Args:
        ticker_symbol (required): Stock ticker or crypto symbol (e.g., "AAPL", "BTC-USD").
        indicator (required): Technical indicator to compute (ema, macd, adx, rsi, stoch, bbands, atr, obv, mfi, sar, typprice, beta, ppo).
        interval (optional): Time interval for analysis. Options: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 4h, 1d, 5d, 1wk, 1mo, 3mo (default: 1d).
        outputsize (optional): Number of data points to return (default: 30).
        benchmark_symbol (optional): Benchmark symbol for beta calculation only.
    """
    
    kwargs = {}
    if indicator == 'beta':
        kwargs['benchmark_symbol'] = benchmark_symbol

    success, data = ctx.context.yfinance_api.calculate_indicator(
        symbol=ticker_symbol, 
        indicator_name=indicator, 
        interval=interval, 
        outputsize=outputsize,
        **kwargs
    )
    if success:
        return data
    else:
        return {"error": data}
