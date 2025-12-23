from agents import RunContextWrapper, function_tool
from src.agent.context import Context
from typing import Literal
from datetime import datetime, timezone
import uuid
from src.services.database import get_async_db_connection


@function_tool
async def get_watchlist(
    ctx: RunContextWrapper[Context],
    watchlist_id: str,
    ):
    """
    Retrieves the list of symbols in a watchlist.

    Args:
        watchlist_id (required): Watchlist ID to filter by.
    """
    async with get_async_db_connection() as conn:
        row = await conn.fetchrow(
            "SELECT assets FROM watchlists WHERE watchlist_id = $1 AND telegram_user_id = $2",
            watchlist_id, ctx.context.user_id
        )
        
        if row is None:
            return {"error": f"Watchlist with ID {watchlist_id} not found."}
        
        assets = row['assets'] if isinstance(row['assets'], list) else []
    
    return assets

@function_tool
async def create_watchlist(
    ctx: RunContextWrapper[Context],
    watchlist_name: str,
    ):
    """
    Creates a new empty watchlist. Returns confirmation when created.

    Args:
        watchlist_name (required): Name for the new watchlist.
    """
    async with get_async_db_connection() as conn:
        # Check if watchlist already exists for this user
        row = await conn.fetchrow(
            "SELECT watchlist_id FROM watchlists WHERE telegram_user_id = $1 AND LOWER(watchlist_name) = LOWER($2)",
            ctx.context.user_id, watchlist_name
        )
        if row is not None:
            return {"error": f"Watchlist '{watchlist_name}' already exists."}

        watchlist_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)
        updated_at = created_at
        
        await conn.execute(
            """INSERT INTO watchlists (
                watchlist_id, telegram_user_id, created_at, watchlist_name, assets, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6)""",
            watchlist_id,
            ctx.context.user_id,
            created_at,
            watchlist_name,
            [],  # Empty list for JSONB column
            updated_at,
        )

    return f"Watchlist with ID {watchlist_id} ({watchlist_name}) created successfully"

@function_tool
async def remove_watchlist(
    ctx: RunContextWrapper[Context],
    watchlist_id: str,
    ):
    """
    Permanently removes a watchlist and all its tracked assets. Returns confirmation when deleted.

    Args:
        watchlist_id (required): Watchlist ID to delete.
    """
    async with get_async_db_connection() as conn:
        # Check if watchlist exists and belongs to user
        row = await conn.fetchrow(
            "SELECT watchlist_id FROM watchlists WHERE watchlist_id = $1 AND telegram_user_id = $2",
            watchlist_id, ctx.context.user_id
        )
        if row is None:
            return {"error": f"Watchlist with ID {watchlist_id} not found."}
        
        # Delete the watchlist
        await conn.execute(
            "DELETE FROM watchlists WHERE watchlist_id = $1 AND telegram_user_id = $2",
            watchlist_id, ctx.context.user_id
        )

    return f"Watchlist with ID {watchlist_id} deleted successfully."

@function_tool
async def modify_watchlist_symbols(
    ctx: RunContextWrapper[Context],
    watchlist_id: str,
    ticker_symbol: str | list[str],
    action: Literal["add", "remove"],
    ):
    """
    Adds or removes one or more assets from a watchlist. Returns confirmation when modified.

    Args:
        watchlist_id (required): Watchlist ID to modify.
        ticker_symbol (required): Single ticker symbol (e.g., "AAPL") or list of symbols (e.g., ["AAPL", "MSFT", "GOOGL"]).
        action (required): Either "add" to add the symbol(s) or "remove" to remove them.
    """ 
    # Handle both single symbol and list of symbols
    symbols = [ticker_symbol] if isinstance(ticker_symbol, str) else ticker_symbol
    symbols_upper = [s.upper() for s in symbols]
    
    async with get_async_db_connection() as conn:
        row = await conn.fetchrow(
            "SELECT assets FROM watchlists WHERE watchlist_id = $1 AND telegram_user_id = $2",
            watchlist_id, ctx.context.user_id
        )
        
        if row is None:
            return {"error": f"Watchlist with ID {watchlist_id} not found."}

        # assets is already a list from JSONB
        current_assets = row['assets'] if isinstance(row['assets'], list) else []
        
        added = []
        removed = []
        skipped = []
        
        if action == "add":
            for symbol in symbols_upper:
                if symbol in current_assets:
                    skipped.append(symbol)
                else:
                    current_assets.append(symbol)
                    added.append(symbol)
        else:  # remove
            for symbol in symbols_upper:
                if symbol not in current_assets:
                    skipped.append(symbol)
                else:
                    current_assets.remove(symbol)
                    removed.append(symbol)
        
        # Build message
        messages = []
        if action == "add":
            if added:
                messages.append(f"Added {', '.join(added)} to watchlist with ID {watchlist_id}.")
            if skipped:
                messages.append(f"Skipped {', '.join(skipped)} (already in watchlist).")
        else:  # remove
            if removed:
                messages.append(f"Removed {', '.join(removed)} from watchlist with ID {watchlist_id}.")
            if skipped:
                messages.append(f"Skipped {', '.join(skipped)} (not in watchlist).")
        
        if not messages:
            return {"error": f"No changes made to watchlist with ID {watchlist_id}."}
        
        updated_at = datetime.now(timezone.utc)
        await conn.execute(
            "UPDATE watchlists SET assets = $1, updated_at = $2 WHERE watchlist_id = $3 AND telegram_user_id = $4",
            current_assets, updated_at, watchlist_id, ctx.context.user_id
        )
    
    return " ".join(messages)
