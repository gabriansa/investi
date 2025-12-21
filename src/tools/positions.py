from agents import RunContextWrapper, function_tool
from src.agent.context import Context
from src.utils import format_api_timestamps


@function_tool
def get_positions(
    ctx: RunContextWrapper[Context],
    ticker_symbols: list[str] | None = None,
    ):
    """
    Retrieves current open positions. Returns position data including symbol, quantity, market value,
    average entry price, current price, unrealized P&L (dollar and percent), today's P&L, and side.

    Args:
        ticker_symbols (optional): List of symbols to retrieve (e.g., ["AAPL", "TSLA", "BTC-USD"]). Omit for all positions.
    """
    if ticker_symbols is None:
        success, response = ctx.context.alpaca_api.get_all_positions()
        if not success:
            return {"error": response['message']}
        
        # Format timestamp fields in all positions
        format_api_timestamps(response)
        return response
    else:
        results = []
        for symbol in ticker_symbols:
            success, response = ctx.context.alpaca_api.get_position_by_symbol(symbol=symbol)
            if not success:
                results.append({
                    "symbol": symbol,
                    "error": response['message']
                })
            else:
                format_api_timestamps(response)
                results.append(response)
        
        return results

@function_tool
def close_position(
    ctx: RunContextWrapper[Context],
    ticker_symbol: str,
    qty: float | None = None,
    percentage: float | None = None,
    ):
    """
    Immediately liquidates a position at current market price. Returns the liquidation order details 
    including filled quantity, execution price, and order status.

    Args:
        ticker_symbol (required): Stock ticker or crypto symbol to liquidate (e.g., "AAPL", "BTC-USD").
        qty (optional): Number of shares/units to liquidate. Mutually exclusive with percentage. Omit both to close entire position.
        percentage (optional): Percentage of position to liquidate (0-100). Mutually exclusive with qty. Omit both to close entire position.
    """
    success, response = ctx.context.alpaca_api.close_position_by_symbol(
        symbol=ticker_symbol,
        qty=qty,
        percentage=percentage
    )

    if not success:
        return {"error": response['message']}
    
    # Format timestamp fields (close_position returns order data)
    format_api_timestamps(response)
    return response
