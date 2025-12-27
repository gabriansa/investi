import uuid
import json
from datetime import datetime, timezone
from typing import Literal
from agents import RunContextWrapper, function_tool
from src.agent.context import Context
from src.services.database import get_async_db_connection
from src.tools.types import RoleLiteral
from src.utils import validate_date, format_timestamp


@function_tool
async def set_one_time_task(
    ctx: RunContextWrapper[Context],
    role: RoleLiteral,
    description: str,
    task_datetime: str,
    ticker_symbol: str | None = None,
    related_note_ids: list[str] | None = None,
    related_task_ids: list[str] | None = None,
    related_watchlist_ids: list[str] | None = None,
    ):
    """
    Schedules a one-time task at a specific future date/time. Returns confirmation when created.

    Args:
        role (required): "portfolio_manager", "analyst" or "trader".
        description (required): Instructions for what to do when the task triggers.
        task_datetime (required): When to trigger, in YYYY-MM-DD HH:MM:SS format. Must be in the future.
        ticker_symbol (optional): Stock/crypto symbol for asset-specific tasks.
        related_note_ids (optional): List of note IDs to link to this task. Omit to not link to any notes.
        related_task_ids (optional): List of task IDs to link to this task. Omit to not link to any tasks.
        related_watchlist_ids (optional): List of watchlist IDs to link to this task. Omit to not link to any watchlists.
    """
    success, task_dt = validate_date(
        task_datetime,
        input_format="%Y-%m-%d %H:%M:%S",
        check_future=True
    )
    if not success:
        return {"error": f"Invalid datetime format. Use YYYY-MM-DD HH:MM:SS format and ensure it's in the future. Current time is {format_timestamp(datetime.now(timezone.utc))}"}

    task_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    
    async with get_async_db_connection() as conn:
        await conn.execute(
            """INSERT INTO tasks (
                task_id, telegram_user_id, created_at, ticker_symbol, role, description,
                task_datetime, is_active, trigger_type, trigger_config,
                related_note_ids, related_task_ids, related_watchlist_ids
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
            task_id,
            ctx.context.user_id,
            created_at,
            ticker_symbol,
            role,
            description,
            task_dt,
            True,  # is_active
            "one_time",
            None,  # trigger_config
            related_note_ids if related_note_ids else [],
            related_task_ids if related_task_ids else [],
            related_watchlist_ids if related_watchlist_ids else [],
        )

    return f"One-time task with ID {task_id} created"

@function_tool
async def set_recurring_task(
    ctx: RunContextWrapper[Context],
    role: RoleLiteral,
    description: str,
    first_task_datetime: str,
    recurrence_type: Literal["day", "week", "month", "year"],
    recurrence_interval: int,
    ends_type: Literal["never", "on", "after"],
    ends_value: str | int | None,
    ticker_symbol: str | None = None,
    related_note_ids: list[str] | None = None,
    related_task_ids: list[str] | None = None,
    related_watchlist_ids: list[str] | None = None,
    ):
    """
    Schedules a recurring task that repeats on a regular cadence. Returns confirmation when created.

    Args:
        role (required): "portfolio_manager", "analyst" or "trader".
        description (required): Instructions for what to do each time the task triggers.
        first_task_datetime (required): First occurrence in YYYY-MM-DD HH:MM:SS format.
        recurrence_type (required): "day", "week", "month", or "year".
        recurrence_interval (required): Every N units (e.g., 2 with "week" = every 2 weeks).
        ends_type (required): "never", "on" (ends on date), or "after" (ends after N occurrences).
        ends_value (optional): Required if ends_type is "on" or "after". Date (YYYY-MM-DD HH:MM:SS) or count.
        ticker_symbol (optional): Stock/crypto symbol for asset-specific tasks.
        related_note_ids (optional): List of note IDs to link to this task. Omit to not link to any notes.
        related_task_ids (optional): List of task IDs to link to this task. Omit to not link to any tasks.
        related_watchlist_ids (optional): List of watchlist IDs to link to this task. Omit to not link to any watchlists.
    """
    success, task_dt = validate_date(
        first_task_datetime,
        input_format="%Y-%m-%d %H:%M:%S",
        check_future=True
    )
    if not success:
        return {"error": f"Invalid datetime format. Use YYYY-MM-DD HH:MM:SS format and ensure it's in the future. Current time is {format_timestamp(datetime.now(timezone.utc))}"}
    
    if ends_type == "on" and ends_value:
        success, ends_value = validate_date(
            ends_value,
            input_format="%Y-%m-%d %H:%M:%S",
            check_future=True
        )
        if not success:
            return {"error": f"Invalid end datetime format. Use YYYY-MM-DD HH:MM:SS format and ensure it's in the future. Current time is {format_timestamp(datetime.now(timezone.utc))}"}
    elif ends_type == "after" and ends_value:
        try:
            int(ends_value)
        except ValueError:
            return {"error": f"Invalid count for ends_value. Must be an integer. Provided: {ends_value}, type: {type(ends_value)}"}

    trigger_config = {
        "type": recurrence_type,
        "interval": recurrence_interval,
        "end_type": ends_type,
        "end_value": None if ends_type == "never" else ends_value
    }
    
    task_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    
    async with get_async_db_connection() as conn:
        await conn.execute(
            """INSERT INTO tasks (
                task_id, telegram_user_id, created_at, ticker_symbol, role, description,
                task_datetime, is_active, trigger_type, trigger_config,
                related_note_ids, related_task_ids, related_watchlist_ids
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
            task_id,
            ctx.context.user_id,
            created_at,
            ticker_symbol,
            role,
            description,
            task_dt,
            True,  # is_active
            "recurring",
            trigger_config,
            related_note_ids if related_note_ids else [],
            related_task_ids if related_task_ids else [],
            related_watchlist_ids if related_watchlist_ids else [],
        )
    
    return f"Recurring task with ID {task_id} created"

@function_tool
async def set_conditional_task(
    ctx: RunContextWrapper[Context],
    role: RoleLiteral,
    description: str,
    condition_type: Literal["price", "cash", "position_value", "position_pnl", "portfolio_value", "position_allocation", "volume"],
    comparison: Literal["above", "below"],
    threshold: float,
    ticker_symbol: str | None = None,
    related_note_ids: list[str] | None = None,
    related_task_ids: list[str] | None = None,
    related_watchlist_ids: list[str] | None = None,
    ):
    """
    Schedules a task that triggers when a market or portfolio condition is met. Returns confirmation when created.

    Args:
        role (required): "portfolio_manager", "analyst" or "trader".
        description (required): Instructions for when the condition is met.
        condition_type (required): "price", "cash", "position_value", "position_pnl", "portfolio_value", "position_allocation", or "volume".
        comparison (required): "above" or "below".
        threshold (required): Value to compare against. Dollar amounts for prices/values, decimals for percentages (e.g., 0.30 for 30%), or volume count.
        ticker_symbol (optional): Required for price, position_value, position_pnl, position_allocation, volume conditions.
        related_note_ids (optional): List of note IDs to link to this task. Omit to not link to any notes.
        related_task_ids (optional): List of task IDs to link to this task. Omit to not link to any tasks.
        related_watchlist_ids (optional): List of watchlist IDs to link to this task. Omit to not link to any watchlists.
    """
    requires_ticker = ["price", "position_value", "position_pnl", "position_allocation", "volume"]
    if condition_type in requires_ticker and not ticker_symbol:
        return {"error": f"ticker_symbol required for condition_type='{condition_type}'"}
    
    trigger_config = {
        "type": condition_type,
        "comparison": comparison,
        "threshold": threshold
    }
    
    task_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    
    # Check if similar conditional task already exists, then create if not
    async with get_async_db_connection() as conn:
        existing = await conn.fetchrow(
            """SELECT task_id FROM tasks 
               WHERE telegram_user_id = $1 
               AND trigger_type = 'conditional'
               AND is_active = true
               AND ticker_symbol = $2
               AND trigger_config->>'type' = $3
               AND trigger_config->>'comparison' = $4
               AND (trigger_config->>'threshold')::float = $5""",
            ctx.context.user_id,
            ticker_symbol,
            condition_type,
            comparison,
            threshold
        )
        
        if existing:
            return {"error": f"A similar conditional task already exists with ID {existing['task_id']}. Remove it first or modify the condition."}
        
        await conn.execute(
            """INSERT INTO tasks (
                task_id, telegram_user_id, created_at, ticker_symbol, role, description,
                task_datetime, is_active, trigger_type, trigger_config,
                related_note_ids, related_task_ids, related_watchlist_ids
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
            task_id,
            ctx.context.user_id,
            created_at,
            ticker_symbol,
            role,
            description,
            None,  # task_datetime is NULL for conditional tasks
            True,  # is_active
            "conditional",
            trigger_config,
            related_note_ids if related_note_ids else [],
            related_task_ids if related_task_ids else [],
            related_watchlist_ids if related_watchlist_ids else [],
        )
    
    return f"Conditional task with ID {task_id} created"

@function_tool
async def get_tasks(
    ctx: RunContextWrapper[Context],
    task_ids: list[str] | None,
    ticker_symbol: str | None,
    is_active: bool | None,
    trigger_type: Literal["one_time", "recurring", "conditional"] | None,
    ):
    """
    Retrieves tasks based on filters. Returns tasks sorted by creation date (oldest first).

    Args:
        task_ids (optional): List of task IDs to filter by. Omit to see all tasks.
        ticker_symbol (optional): Filter by asset (e.g., "AAPL", "BTC-USD").
        is_active (optional): True for pending, False for completed/triggered tasks.
        trigger_type (optional): "one_time", "recurring", or "conditional".
    """
    if not task_ids and not ticker_symbol and not is_active and not trigger_type:
        return {"error": "At least one filter (task_ids, ticker_symbol, is_active, or trigger_type) must be provided."}
    
    async with get_async_db_connection() as conn:
        # Build query
        query = "SELECT * FROM tasks WHERE telegram_user_id = $1"
        params = [ctx.context.user_id]
        param_counter = 2
        
        # Apply filters
        if task_ids:
            placeholders = ','.join([f'${i}' for i in range(param_counter, param_counter + len(task_ids))])
            query += f" AND task_id IN ({placeholders})"
            params.extend(task_ids)
            param_counter += len(task_ids)
        
        if ticker_symbol:
            query += f" AND LOWER(ticker_symbol) = LOWER(${param_counter})"
            params.append(ticker_symbol)
            param_counter += 1
        
        if trigger_type:
            query += f" AND trigger_type = ${param_counter}"
            params.append(trigger_type)
            param_counter += 1
        
        if is_active is not None:
            query += f" AND is_active = ${param_counter}"
            params.append(is_active)
            param_counter += 1
        
        query += " ORDER BY created_at"
        
        rows = await conn.fetch(query, *params)
        tasks = [dict(row) for row in rows]
    
    if not tasks:
        return {"error": "No tasks found for the given filters"}
    
    # Format timestamps
    for task in tasks:
        task['created_at'] = format_timestamp(task['created_at'])
        if task.get('task_datetime'):  # task_datetime can be NULL
            task['task_datetime'] = format_timestamp(task['task_datetime'])
        # JSONB fields (trigger_config, related_*_ids) are already dicts/lists from asyncpg
    
    return tasks

@function_tool
async def remove_task(
    ctx: RunContextWrapper[Context],
    task_id: list[str],
    ):
    """
    Permanently removes one or more tasks. Returns confirmation when deleted.

    Args:
        task_id (required): List of task IDs to delete (e.g., ["uuid1"] for single or ["uuid1", "uuid2", "uuid3"] for multiple). Obtain from get_tasks.
    """
    results = {}
    async with get_async_db_connection() as conn:
        for tid in task_id:
            # Check if task exists and belongs to user
            row = await conn.fetchrow(
                "SELECT task_id FROM tasks WHERE task_id = $1 AND telegram_user_id = $2",
                tid, ctx.context.user_id
            )
            if row is None:
                results[tid] = {"error": f"Task with ID {tid} not found"}
            else:
                # Delete the task
                await conn.execute(
                    "DELETE FROM tasks WHERE task_id = $1 AND telegram_user_id = $2",
                    tid, ctx.context.user_id
                )
                results[tid] = f"Task with ID {tid} deleted successfully"
    
    return results

