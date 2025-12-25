import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta

from src.agent.agent import InvestiAgent
from src.api.alpaca import AlpacaAPI
from src.api.yahoo_finance import YFinanceAPI
from src.services.database import get_async_db_connection
from src.services.user_service import UserService
from src.utils import format_timestamp

logger = logging.getLogger(__name__)

# Track first failure time for each ticker/task to detect persistent issues
_failure_tracking = {}  # (ticker, task_id, type) -> first_failure_timestamp


def _track_failure(ticker: str, task_id: str, failure_type: str, user_id: int):
    """Track a failure and log if it's been failing for >10 minutes."""
    key = (ticker, task_id, failure_type)
    now = datetime.now(timezone.utc)
    
    if key not in _failure_tracking:
        # First failure - just track it, don't log
        _failure_tracking[key] = now
    else:
        # Check if it's been failing for >10 minutes
        first_failure = _failure_tracking[key]
        if (now - first_failure).total_seconds() >= 600:  # 10 minutes
            logger.warning(f"Persistent failure (>10min) getting {failure_type} for {ticker} (task {task_id}, user {user_id})")
            # Reset tracking so we don't spam logs - will warn again if still failing in another 10min
            _failure_tracking[key] = now

async def check_tasks(send_message_callback, config: dict):
    """
    Main task loop - collects triggered tasks, groups by user, and executes them sequentially per user.
    """
    task_check_interval_seconds = config['tasks']['task_check_interval_seconds']
    min_credits_to_run = config['credits']['min_credits_to_run']

    user_queues = {}
    queued_task_ids = set()
    
    async def process_user_tasks(user_id: int, queue: asyncio.Queue):
        """Process all tasks for a user sequentially, then cleanup."""
        while True:
            try:
                task = await asyncio.wait_for(queue.get(), timeout=5.0)
                await _execute_task(task, send_message_callback, min_credits_to_run, queued_task_ids, config)
            except asyncio.TimeoutError:
                if queue.empty():
                    break
            except Exception as e:
                logger.error(f"Error executing task for user {user_id}: {e}")
        user_queues.pop(user_id, None)
    
    while True:
        try:
            # Only query tasks that are:
            # 1. Conditional (always need to check)
            # 2. One-time or recurring with task_datetime <= NOW (due)            
            async with get_async_db_connection() as conn:
                active_tasks = await conn.fetch(
                    """
                    SELECT tasks.*, users.alpaca_api_key, users.alpaca_secret_key, users.openrouter_api_key
                    FROM tasks
                    JOIN users ON tasks.telegram_user_id = users.telegram_user_id
                    WHERE tasks.is_active = TRUE
                    AND (
                        tasks.trigger_type = 'conditional'
                        OR tasks.task_datetime <= $1
                    )
                    """,
                    datetime.now(timezone.utc)
                )
            
            # Collect and group triggered tasks by user
            triggered_by_user = {}
            for task in active_tasks:
                if task['trigger_type'] == 'one_time':
                    triggered = datetime.now(timezone.utc) >= task['task_datetime']
                elif task['trigger_type'] == 'recurring':
                    triggered = datetime.now(timezone.utc) >= task['task_datetime']
                elif task['trigger_type'] == 'conditional':
                    triggered = await _check_conditional_task(task)
                else:
                    triggered = False
                    
                if triggered:
                    user_id = task['telegram_user_id']
                    triggered_by_user.setdefault(user_id, []).append(dict(task))
            
            # Add tasks to user queues (create worker if needed)
            for user_id, tasks in triggered_by_user.items():
                if user_id not in user_queues:
                    user_queues[user_id] = asyncio.Queue()
                    asyncio.create_task(process_user_tasks(user_id, user_queues[user_id]))
                for task in tasks:
                    if task['task_id'] not in queued_task_ids:
                        queued_task_ids.add(task['task_id'])
                        user_queues[user_id].put_nowait(task)
        
        except Exception as e:
            logger.error(f"Error checking tasks: {e}")
        
        await asyncio.sleep(task_check_interval_seconds)

async def _check_conditional_task(task) -> bool:
    """Check if a conditional task's condition is met."""
    trigger_config = task['trigger_config']
    condition_type = trigger_config['type']
    comparison = trigger_config['comparison']
    threshold = trigger_config['threshold']
    ticker = task['ticker_symbol'] if task['ticker_symbol'] else None
    
    current_value = await _get_condition_value(condition_type, ticker, task)
    if current_value is None:
        return False
    
    if comparison == 'above':
        return current_value > threshold
    elif comparison == 'below':
        return current_value < threshold
    return False

async def _get_condition_value(condition_type: str, ticker: str, task: dict) -> float | None:
    """Get the current value for a conditional task check."""
    try:
        alpaca_api = AlpacaAPI(
            api_key=task['alpaca_api_key'],
            secret_key=task['alpaca_secret_key']
        )

        if condition_type == 'price':
            success, data = await asyncio.to_thread(YFinanceAPI().quote, symbol=ticker, interval="1m")
            
            if success:
                # Clear failure tracking on success
                _failure_tracking.pop((ticker, task['task_id'], 'price'), None)
                return float(data.get('close', 0))
            
            # Failed - track it
            _track_failure(ticker, task['task_id'], 'price', task['telegram_user_id'])
        
        elif condition_type == 'cash':
            success, data = await asyncio.to_thread(alpaca_api.get_account)
            if success:
                return float(data.get('cash', 0))
            else:
                logger.warning(f"Failed to get cash balance (task {task['task_id']}, user {task['telegram_user_id']}): {data}")
        
        elif condition_type == 'portfolio_value':
            success, data = await asyncio.to_thread(alpaca_api.get_account)
            if success:
                return float(data.get('equity', 0))
            else:
                logger.warning(f"Failed to get portfolio value (task {task['task_id']}, user {task['telegram_user_id']}): {data}")
        
        elif condition_type == 'position_value':
            success, data = await asyncio.to_thread(alpaca_api.get_position_by_symbol, ticker)
            if success:
                return float(data.get('market_value', 0))
            else:
                logger.warning(f"Failed to get position value for {ticker} (task {task['task_id']}, user {task['telegram_user_id']}): {data}")
        
        elif condition_type == 'position_pnl':
            success, data = await asyncio.to_thread(alpaca_api.get_position_by_symbol, ticker)
            if success:
                return float(data.get('unrealized_plpc', 0))
            else:
                logger.warning(f"Failed to get position P&L for {ticker} (task {task['task_id']}, user {task['telegram_user_id']}): {data}")
        
        elif condition_type == 'position_allocation':
            pos_success, pos_data = await asyncio.to_thread(alpaca_api.get_position_by_symbol, ticker)
            acc_success, acc_data = await asyncio.to_thread(alpaca_api.get_account)
            if pos_success and acc_success:
                market_value = float(pos_data.get('market_value', 0))
                equity = float(acc_data.get('equity', 1))
                return market_value / equity if equity > 0 else 0
            else:
                if not pos_success:
                    logger.warning(f"Failed to get position for {ticker} (task {task['task_id']}, user {task['telegram_user_id']}): {pos_data}")
                if not acc_success:
                    logger.warning(f"Failed to get account data (task {task['task_id']}, user {task['telegram_user_id']}): {acc_data}")
        
        elif condition_type == 'volume':
            success, data = await asyncio.to_thread(YFinanceAPI().quote, symbol=ticker, interval="1m")
            
            if success:
                # Clear failure tracking on success
                _failure_tracking.pop((ticker, task['task_id'], 'volume'), None)
                return float(data.get('volume', 0))
            
            # Failed - track it
            _track_failure(ticker, task['task_id'], 'volume', task['telegram_user_id'])
        
        return None
    except Exception as e:
        logger.error(f"Error checking condition value for task {task.get('task_id', 'unknown')}, user {task.get('telegram_user_id', 'unknown')}: {e}", exc_info=True)
        return None

async def _execute_task(task, send_message_callback, min_credits_to_run: float, queued_task_ids: set, config: dict = None):
    """Execute a triggered task - notify and run the agent."""
    task_id = task['task_id']
    ticker = task['ticker_symbol'] if task['ticker_symbol'] else None
    description = task['description']
    trigger_type = task['trigger_type']
    telegram_user_id = task['telegram_user_id']
    
    logger.info(f"Task triggered for user {telegram_user_id}: ID={task_id}, Type={trigger_type}, Ticker={ticker or 'None'}")
    
    # Save original state for rollback if execution fails
    original_state = {
        'is_active': task['is_active'],
        'task_datetime': task.get('task_datetime'),
        'trigger_config': task.get('trigger_config')
    }
    
    # CRITICAL: Mark as completed/reschedule in DB FIRST to prevent re-triggering
    # This ensures that any check cycle that runs during execution sees updated state
    await _mark_task_completed(task)
    
    # Build trigger message
    trigger_message = f"🔔 **{trigger_type.replace('_', ' ').title()} Task**"
    if ticker:
        trigger_message += f" ({ticker})"
    trigger_message += f"\n\n**Description:**\n{description}"

    # Check credits before running
    user_service = UserService()
    has_enough_credits, message = await asyncio.to_thread(
        user_service.has_enough_credits, task['openrouter_api_key'], min_credits_to_run
    )
    if not has_enough_credits:
        logger.warning(f"Task {task_id} for user {telegram_user_id} skipped: insufficient credits")
        # Rollback task state since we didn't execute
        await _rollback_task_state(task_id, original_state)
        queued_task_ids.discard(task_id)
        await send_message_callback(trigger_message + "\n\n**Couldn't run:**\n" + message, telegram_user_id)
        return
    
    await send_message_callback(trigger_message, task['telegram_user_id'])
    
    # Build context for the agent - only include relevant task fields
    keep_fields = [
        'task_id', 'created_at', 'ticker_symbol', 'role', 'description',
        'task_datetime', 'trigger_type', 'trigger_config', 'related_note_ids',
        'related_task_ids', 'related_watchlist_ids'
    ]
    task_context = {field: task[field] for field in keep_fields if field in task}
    
    # Custom JSON encoder for datetime objects
    def datetime_encoder(obj):
        if isinstance(obj, datetime):
            return format_timestamp(obj)
        return str(obj)
    
    agent = InvestiAgent(
        config=config,
        user_id=task['telegram_user_id'],
        alpaca_api_key=task['alpaca_api_key'],
        alpaca_secret_key=task['alpaca_secret_key'],
        openrouter_api_key=task['openrouter_api_key'],
    )

    try:
        message = f"<task_triggered>\n{json.dumps(task_context, indent=2, default=datetime_encoder)}\n</task_triggered>"
        result = await agent.run(message, use_session=False)
        await send_message_callback(result, telegram_user_id)
        logger.info(f"Task {task_id} completed for user {telegram_user_id}")
    except Exception as e:
        logger.error(f"Task {task_id} execution failed for user {telegram_user_id}: {e}", exc_info=True)
        # Rollback task state on failure so it can retry
        await _rollback_task_state(task_id, original_state)
        raise
    finally:
        # Always remove from queue after execution attempt (success or fail)
        queued_task_ids.discard(task_id)

async def _rollback_task_state(task_id: str, original_state: dict):
    """Rollback task to original state if execution fails."""
    async with get_async_db_connection() as conn:
        if original_state.get('trigger_config'):
            # Recurring task - restore datetime and config
            await conn.execute(
                "UPDATE tasks SET is_active = $1, task_datetime = $2, trigger_config = $3 WHERE task_id = $4",
                original_state['is_active'],
                original_state['task_datetime'],
                original_state['trigger_config'],
                task_id
            )
        else:
            # One-time or conditional - just restore is_active
            await conn.execute(
                "UPDATE tasks SET is_active = $1 WHERE task_id = $2",
                original_state['is_active'],
                task_id
            )

async def _mark_task_completed(task):
    """Update task in DB after successful execution."""
    task_id = task['task_id']
    trigger_type = task['trigger_type']
    
    async with get_async_db_connection() as conn:
        if trigger_type == 'one_time' or trigger_type == 'conditional':
            await conn.execute("UPDATE tasks SET is_active = FALSE WHERE task_id = $1", task_id)
        
        elif trigger_type == 'recurring':
            task_dt = task['task_datetime']
            trigger_config = task['trigger_config']
            
            # Calculate next occurrence
            if trigger_config['type'] == 'day':
                next_dt = task_dt + timedelta(days=trigger_config['interval'])
            elif trigger_config['type'] == 'week':
                next_dt = task_dt + timedelta(weeks=trigger_config['interval'])
            elif trigger_config['type'] == 'month':
                next_dt = task_dt + relativedelta(months=trigger_config['interval'])
            elif trigger_config['type'] == 'year':
                next_dt = task_dt + relativedelta(years=trigger_config['interval'])
            
            # Check if recurrence should end
            if trigger_config['end_type'] == 'on':
                end_dt = trigger_config['end_value']
                if next_dt > end_dt:
                    await conn.execute("UPDATE tasks SET is_active = FALSE WHERE task_id = $1", task_id)
                else:
                    await conn.execute("UPDATE tasks SET task_datetime = $1 WHERE task_id = $2", next_dt, task_id)
            elif trigger_config['end_type'] == 'after':
                remaining = trigger_config['end_value'] - 1
                if remaining <= 0:
                    await conn.execute("UPDATE tasks SET is_active = FALSE WHERE task_id = $1", task_id)
                else:
                    trigger_config['end_value'] = remaining
                    await conn.execute("UPDATE tasks SET trigger_config = $1, task_datetime = $2 WHERE task_id = $3", trigger_config, next_dt, task_id)
            else:  # end_type == 'never'
                await conn.execute("UPDATE tasks SET task_datetime = $1 WHERE task_id = $2", next_dt, task_id)
