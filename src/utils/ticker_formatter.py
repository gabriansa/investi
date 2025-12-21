import aiohttp
import asyncio

async def _check_exchange(session: aiohttp.ClientSession, symbol: str, exchange: str) -> tuple[str, bool]:
    """Check if a symbol exists on a given exchange."""
    url = f"https://www.google.com/finance/quote/{symbol}:{exchange}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as response:
            if response.status == 200:
                text = await response.text()
                return url, "couldn't find any match" not in text.lower()
    except:
        pass
    return url, False

async def _format_ticker_link_async(session: aiohttp.ClientSession, symbol: str) -> str:
    """Async version of format_ticker_link."""
    if not symbol:
        return ""
    
    # For crypto (has dash), use symbol only
    if '-' in symbol:
        return f"[{symbol}](https://www.google.com/finance/quote/{symbol})"
    
    # Try NASDAQ first
    nasdaq_url, nasdaq_valid = await _check_exchange(session, symbol, "NASDAQ")
    if nasdaq_valid:
        return f"[{symbol}]({nasdaq_url})"
    
    # Try NYSE
    nyse_url, nyse_valid = await _check_exchange(session, symbol, "NYSE")
    if nyse_valid:
        return f"[{symbol}]({nyse_url})"
    
    # Fallback: symbol only
    return f"[{symbol}](https://www.google.com/finance/quote/{symbol})"

def format_ticker_link(symbol: str) -> str:
    """
    Format a ticker symbol as a Telegram markdown hyperlink to Google Finance.
    Synchronous wrapper around async implementation.
    
    Args:
        symbol: The ticker symbol (e.g., "AAPL", "NKE")
    
    Returns:
        Markdown formatted link to Google Finance with correct exchange
    """
    return asyncio.run(format_ticker_links([symbol]))[symbol] if symbol else ""

async def format_ticker_links_async(symbols: list[str]) -> dict[str, str]:
    """
    Format multiple ticker symbols as Telegram markdown hyperlinks concurrently.
    
    Args:
        symbols: List of ticker symbols
    
    Returns:
        Dictionary mapping symbol to formatted markdown link
    """
    if not symbols:
        return {}
    
    async with aiohttp.ClientSession() as session:
        tasks = [_format_ticker_link_async(session, symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        return dict(zip(symbols, results))

def format_ticker_links(symbols: list[str]) -> dict[str, str]:
    """
    Format multiple ticker symbols as Telegram markdown hyperlinks concurrently.
    Synchronous wrapper around async implementation.
    
    Args:
        symbols: List of ticker symbols
    
    Returns:
        Dictionary mapping symbol to formatted markdown link
    """
    return asyncio.run(format_ticker_links_async(symbols))
