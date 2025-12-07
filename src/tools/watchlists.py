from agents import RunContextWrapper, function_tool
from src.agent.context import Context
from typing import Literal
from datetime import datetime, timezone
import json
import uuid
from src.services.database import get_db_connection


@function_tool
def get_watchlist(
    ctx: RunContextWrapper[Context],
    watchlist_id: str,
    ):
    """
    Retrieves a watchlist with all tracked assets and their details. Returns watchlist metadata 
    (created_at, updated_at) plus asset information including tradability, asset type, and exchange.

    Args:
        watchlist_id (required): Watchlist ID to filter by.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM watchlists WHERE watchlist_id = ? AND telegram_user_id = ?",
            (watchlist_id, ctx.context.user_id)
        )
        row = cursor.fetchone()
        
        if row is None:
            return {"error": f"Watchlist with ID {watchlist_id} not found."}
        
        watchlist = dict(row)
        assets = json.loads(watchlist['assets']) if watchlist['assets'] else []
    
    # Build result dict
    result = {
        "watchlist_name": watchlist['watchlist_name'],
        "created_at": watchlist['created_at'],
        "updated_at": watchlist['updated_at'],
        "assets": []
    }
    
    # Check if there are any assets
    if not assets:
        return result
    
    # Fetch details for each asset
    for asset in assets:
        success, asset_data = ctx.context.alpaca_api.get_asset_by_symbol(symbol=asset.upper())
        if success:
            result["assets"].append(asset_data)
        else:
            result["assets"].append({"symbol": asset, "error": "Could not fetch asset details"})
    
    return result

@function_tool
def create_watchlist(
    ctx: RunContextWrapper[Context],
    watchlist_name: str,
    ):
    """
    Creates a new empty watchlist. Returns confirmation when created.

    Args:
        watchlist_name (required): Name for the new watchlist.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Check if watchlist already exists for this user
        cursor.execute(
            "SELECT watchlist_id FROM watchlists WHERE telegram_user_id = ? AND LOWER(watchlist_name) = LOWER(?)",
            (ctx.context.user_id, watchlist_name)
        )
        if cursor.fetchone() is not None:
            return {"error": f"Watchlist '{watchlist_name}' already exists."}

        watchlist_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        updated_at = created_at
        
        cursor.execute(
            """INSERT INTO watchlists (
                watchlist_id, telegram_user_id, created_at, watchlist_name, assets, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                watchlist_id,
                ctx.context.user_id,
                created_at,
                watchlist_name,
                json.dumps([]),
                updated_at,
            )
        )

    return f"Watchlist with ID {watchlist_id} ({watchlist_name}) created successfully"

@function_tool
def remove_watchlist(
    ctx: RunContextWrapper[Context],
    watchlist_id: str,
    ):
    """
    Permanently removes a watchlist and all its tracked assets. Returns confirmation when deleted.

    Args:
        watchlist_id (required): Watchlist ID to delete.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Check if watchlist exists and belongs to user
        cursor.execute(
            "SELECT watchlist_id FROM watchlists WHERE watchlist_id = ? AND telegram_user_id = ?",
            (watchlist_id, ctx.context.user_id)
        )
        if cursor.fetchone() is None:
            return {"error": f"Watchlist with ID {watchlist_id} not found."}
        
        # Delete the watchlist
        cursor.execute(
            "DELETE FROM watchlists WHERE watchlist_id = ? AND telegram_user_id = ?",
            (watchlist_id, ctx.context.user_id)
        )

    return f"Watchlist with ID {watchlist_id} deleted successfully."

@function_tool
def modify_watchlist_symbols(
    ctx: RunContextWrapper[Context],
    watchlist_id: str,
    ticker_symbol: str,
    action: Literal["add", "remove"],
    ):
    """
    Adds or removes an asset from a watchlist. Returns confirmation when modified.

    Args:
        watchlist_id (required): Watchlist ID to modify.
        ticker_symbol (required): Stock ticker or crypto symbol (e.g., "AAPL", "BTC-USD").
        action (required): Either "add" to add the symbol or "remove" to remove it.
    """ 
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT assets FROM watchlists WHERE watchlist_id = ? AND telegram_user_id = ?",
            (watchlist_id, ctx.context.user_id)
        )
        row = cursor.fetchone()
        
        if row is None:
            return {"error": f"Watchlist with ID {watchlist_id} not found."}

        current_assets = json.loads(row['assets']) if row['assets'] else []
        symbol_upper = ticker_symbol.upper()
        
        if action == "add":
            if symbol_upper in current_assets:
                return {"error": f"{symbol_upper} already in watchlist with ID {watchlist_id}."}
            current_assets.append(symbol_upper)
            message = f"Added {symbol_upper} to watchlist with ID {watchlist_id}."
        else:  # remove
            if symbol_upper not in current_assets:
                return {"error": f"{symbol_upper} not found in watchlist with ID {watchlist_id}."}
            current_assets.remove(symbol_upper)
            message = f"Removed {symbol_upper} from watchlist with ID {watchlist_id}."
        
        updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        cursor.execute(
            "UPDATE watchlists SET assets = ?, updated_at = ? WHERE watchlist_id = ? AND telegram_user_id = ?",
            (json.dumps(current_assets), updated_at, watchlist_id, ctx.context.user_id)
        )
    
    return message
