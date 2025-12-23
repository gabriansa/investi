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
    ticker_symbol: str | list[str],
    interval: Literal["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "4h", "1d", "5d", "1wk", "1mo", "3mo"],
    rolling_period_hours: int = 24,
    ):
    """
    Retrieves a real-time snapshot of current market data for one or more ticker symbols.
    Returns key metrics including: current price, open/high/low/close, volume, average volume,
    price change (absolute and percent), previous close, 52-week high/low range, extended hours
    pricing, exchange info, and currency. Use this for quick market overviews or current state checks.

    Args:
        ticker_symbol (required): Single ticker symbol (e.g., "AAPL") or list of symbols (e.g., ["AAPL", "MSFT", "GOOGL"]).
        interval (required): Time interval for quote data. Options: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 4h, 1d, 5d, 1wk, 1mo, 3mo.
        rolling_period_hours (optional): Time window in hours to calculate rolling price change (default: 24).
    """
    # Handle both single symbol and list of symbols
    symbols = [ticker_symbol] if isinstance(ticker_symbol, str) else ticker_symbol
    
    results = {}
    for symbol in symbols:
        success, data = ctx.context.yfinance_api.quote(
            symbol=symbol, 
            interval=interval, 
            rolling_period=rolling_period_hours
        )
        results[symbol] = data if success else {"error": data}
    
    # Return unwrapped result for single symbol (backward compatible)
    return results[symbols[0]] if len(symbols) == 1 else results

@function_tool
async def find_screeners(
    ctx: RunContextWrapper[Context],
    search_query: str | list[str],
    ):
    """
    Finds available screeners using natural language search.
    Returns a list of screener names and descriptions that can then be used with execute_screener.
    
    Args:
        search_query (required): Single search query (e.g., "tech gainers") or list of queries (e.g., ["tech gainers", "crypto stats", "dividend stocks"]).
    """
    # Handle both single query and list of queries
    queries = [search_query] if isinstance(search_query, str) else search_query
    
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
    for query in queries:
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
    
    # Return unwrapped result for single query (backward compatible)
    return results[queries[0]] if len(queries) == 1 else results
    
@function_tool
def execute_screener(
    ctx: RunContextWrapper[Context],
    screener_name: str,
    outputsize: int = 10,
    ):
    """
    Executes a screener and returns the ranked results. Use find_screeners first to find valid screener names.
    Returns a ranked list of symbols matching the screener criteria.

    Args:
        screener_name (required): The exact screener name to execute (obtained from screener discovery tools).
        outputsize (optional): Number of results to return (default: 10).
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

    success, data = ctx.context.yfinance_api.screener(
        screener_name=screener_name,
        outputsize=outputsize
    )
    if success:
        # Filter to keep only relevant fields
        filtered_values = [
            {k: v for k, v in record.items() if k in KEEP_FIELDS}
            for record in data.get("values", [])
        ]
        data["values"] = filtered_values
        return data
    else:
        return {"error": data}

@function_tool
def search_for_symbols(
    ctx: RunContextWrapper[Context],
    search_query: str, 
    outputsize: int = 10,
    ):
    """
    Searches for ticker symbols by matching against the ticker itself using similarity scoring.
    Use when you have a guessed ticker symbol and want to find the correct or similar tickers.
    Returns matching symbols with basic info (name, exchange, type) sorted by similarity.

    Args:
        search_query (required): Guessed ticker symbol (e.g., "AAPL", "BTC-USD", "TSLA").
        outputsize (optional): Maximum number of results to return, 1-50 (default: 10).
    """
    if outputsize > 50 or outputsize < 1:
        return {"error": f"outputsize must be between 1 and 50, got {outputsize}"}
    
    success, data = ctx.context.alpaca_api.symbol_search(query=search_query, outputsize=outputsize)
    if success:
        return data
    else:
        return {"error": data}

@function_tool
def get_company_profile(
    ctx: RunContextWrapper[Context],
    ticker_symbol: str | list[str],
    ):
    """
    Retrieves comprehensive company/asset information for fundamental research.
    Returns: business description, sector, industry, headquarters, executive team, market cap,
    P/E ratios, dividend info, 52-week performance, analyst ratings, revenue, margins, and more.
    Use to understand what a company does or gather fundamentals for investment decisions.

    Args:
        ticker_symbol (required): Single ticker symbol (e.g., "AAPL") or list of symbols (e.g., ["AAPL", "MSFT", "GOOGL"]).
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
    
    # Handle both single symbol and list of symbols
    symbols = [ticker_symbol] if isinstance(ticker_symbol, str) else ticker_symbol
    
    results = {}
    for symbol in symbols:
        success, data = ctx.context.yfinance_api.profile(symbol=symbol)
        if success:
            # Filter to keep only relevant fields
            filtered_data = {k: v for k, v in data.items() if k in KEEP_FIELDS}
            results[symbol] = filtered_data
        else:
            results[symbol] = {"error": data}
    
    # Return unwrapped result for single symbol (backward compatible)
    return results[symbols[0]] if len(symbols) == 1 else results

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
