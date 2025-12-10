from typing import Literal
from agents import RunContextWrapper, function_tool
from src.agent.context import Context
from src.utils import format_api_timestamps
from pydantic import BaseModel


class StopLoss(BaseModel):
    stop_price: float
    limit_price: float

class TakeProfit(BaseModel):
    limit_price: float

@function_tool
def create_order(
    ctx: RunContextWrapper[Context],
    ticker_symbol: str,
    side: Literal["buy", "sell"],
    order_type: Literal["market", "limit", "stop", "stop_limit", "trailing_stop"],
    time_in_force: Literal["day", "gtc", "opg", "cls", "ioc", "fok"],
    qty: float | None = None,
    notional: float | None = None,
    limit_price: float | None = None,
    stop_price: float | None = None,
    trail_price: float | None = None,
    trail_percent: float | None = None,
    extended_hours: bool = False,
    order_class: Literal["simple", "oco", "oto", "bracket", ""] = "simple",
    take_profit: TakeProfit | None = None,
    stop_loss: StopLoss | None = None,
    ):
    """
    Creates an order to buy or sell stocks or crypto. Returns order details including order ID, status, 
    filled quantity, and timestamps.

    Args:
        ticker_symbol (required): Stock ticker or crypto pair to trade (e.g., "AAPL", "BTC-USD").
        side (required): Which side of the trade - "buy" to open/add to position, "sell" to close/reduce position.
        order_type (required): Type of order execution - "market" (immediate at current price), "limit" (at specified price or better), "stop" (triggers market order at stop_price), "stop_limit" (triggers limit order at stop_price), "trailing_stop" (follows price by trail amount). Equity supports all types; crypto supports market, limit, stop_limit only.
        time_in_force (required): How long order remains active - "day" (valid during trading day, cancels if unfilled), "gtc" (good til canceled), "opg" (execute in opening auction only), "cls" (execute in closing auction only), "ioc" (immediate or cancel), "fok" (fill or kill - must fill completely or cancel). Equity supports all; crypto supports gtc and ioc only.
        qty (optional): Number of shares/units to trade. Can be fractional for market orders with day time_in_force. Mutually exclusive with notional.
        notional (optional): Dollar amount to trade instead of quantity. Only works with market orders and day time_in_force. Mutually exclusive with qty.
        limit_price (optional): Price limit for order execution. Required for "limit" and "stop_limit" order types.
        stop_price (optional): Price that triggers the order. Required for "stop" and "stop_limit" order types.
        trail_price (optional): Dollar amount to trail behind market price for trailing_stop orders. Either this or trail_percent required for trailing_stop.
        trail_percent (optional): Percentage to trail behind market price for trailing_stop orders. Either this or trail_price required for trailing_stop.
        extended_hours (optional): If true, order can execute in pre-market (4:00-9:30am ET) or after-hours (4:00-8:00pm ET). Only works with "limit" order type and "day" time_in_force (default: false).
        order_class (optional): Order structure - "simple" (single order), "oco" (one-cancels-other, two orders where filling one cancels the other), "oto" (one-triggers-other, second order placed when first fills), "bracket" (entry with both take-profit and stop-loss). Equity supports all; crypto supports simple only (default: "simple").
        take_profit (optional): Take-profit parameters for bracket/oto orders. Provide limit_price to automatically sell at profit target.
        stop_loss (optional): Stop-loss parameters for bracket/oto orders. Provide stop_price and limit_price to automatically limit losses.
    """

    # Convert Pydantic models to dicts if present
    take_profit_dict = take_profit.model_dump() if take_profit else None
    stop_loss_dict = stop_loss.model_dump() if stop_loss else None
    
    success, response = ctx.context.alpaca_api.create_order(
        symbol=ticker_symbol,
        qty=qty,
        notional=notional,
        side=side,
        type=order_type,
        time_in_force=time_in_force,
        limit_price=limit_price,
        stop_price=stop_price,
        trail_price=trail_price,
        trail_percent=trail_percent,
        extended_hours=extended_hours,
        order_class=order_class,
        take_profit=take_profit_dict,
        stop_loss=stop_loss_dict,
    )

    if success:
        # Format timestamp fields to our standard format
        format_api_timestamps(response)
        return response
    else:
        return {"error": response['message']}

@function_tool
def get_orders(
    ctx: RunContextWrapper[Context],
    status: Literal["open", "closed"] = "open",
    ticker_symbols: list[str] | None = None,
    side: Literal["buy", "sell"] | None = None,
    ):
    """
    Retrieves orders based on status, symbols, and side filters. Returns order details including 
    order ID, symbol, quantity, price, status, filled quantity, and timestamps.

    Args:
        status (optional): Filter by order lifecycle state - "open" (pending/partially filled orders that can still execute), "closed" (filled, canceled, or expired orders), (default: "open").
        ticker_symbols (optional): List of ticker symbols to filter by (e.g., ["AAPL", "TSLA", "BTC-USD"]). Omit to see orders across all symbols.
        side (optional): Filter by order direction - "buy" (orders to purchase/open positions) or "sell" (orders to close/reduce positions). Omit to see both.
    """
    success, response = ctx.context.alpaca_api.get_orders(
        status=status,
        symbols=ticker_symbols,
        side=side
    )
    
    if not success:
        return {"error": response['message']}
    
    # Format timestamp fields in all orders
    format_api_timestamps(response)
    return response

@function_tool
def cancel_orders(
    ctx: RunContextWrapper[Context],
    order_ids: list[str],
    ):
    """
    Cancels one or multiple pending orders. Only open orders can be deleted. Returns success/failure 
    status and error messages for each order ID.

    Args:
        order_ids (required): List of order IDs to cancel. Obtain from get_orders.
    """
    results = []
    for order_id in order_ids:
        success, response = ctx.context.alpaca_api.delete_order_by_id(
            order_id=order_id
        )
        results.append({
            "order_id": order_id,
            "success": True if success else False,
            "message": response['message']
        })
        
    return results
