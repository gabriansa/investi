from datetime import datetime, timezone, timedelta
import json
import asyncio
import logging
from dateutil.relativedelta import relativedelta
from src.api.yahoo_finance import YFinanceAPI
from src.api.alpaca import AlpacaAPI
from src.services.database import get_db_connection
from src.services.user_service import UserService
from src.agent.agent import InvestiAgent

logger = logging.getLogger(__name__)


async def check_tasks(send_message_callback, config: dict):
    """
    Main task loop - collects triggered tasks, groups by user, and executes them sequentially per user.
    """
    task_check_interval_seconds = config['tasks']['task_check_interval_seconds']
    min_credits_to_run = config['credits']['min_credits_to_run']

    user_queues = {}
    queued_task_ids = set()
    
    async def process_user_tasks(user_id: str, queue: asyncio.Queue):
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
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT tasks.*, users.alpaca_api_key, users.alpaca_secret_key, users.openrouter_api_key
                    FROM tasks
                    JOIN users ON tasks.telegram_user_id = users.telegram_user_id
                    WHERE tasks.is_active = 1
                """)
                active_tasks = cursor.fetchall()
            
            # Collect and group triggered tasks by user
            triggered_by_user = {}
            for task in active_tasks:
                triggered = (
                    _check_one_time_task(task) if task['trigger_type'] == 'one_time' else
                    _check_recurring_task(task) if task['trigger_type'] == 'recurring' else
                    _check_conditional_task(task) if task['trigger_type'] == 'conditional' else False
                )
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

def _check_one_time_task(task) -> bool:
    """Check if a one-time task should trigger based on datetime."""
    task_dt = datetime.strptime(task['task_datetime'], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= task_dt

def _check_recurring_task(task) -> bool:
    """Check if a recurring task should trigger based on datetime."""
    task_dt = datetime.strptime(task['task_datetime'], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= task_dt

def _check_conditional_task(task) -> bool:
    """Check if a conditional task's condition is met."""
    trigger_config = json.loads(task['trigger_config'])
    condition_type = trigger_config['type']
    comparison = trigger_config['comparison']
    threshold = float(trigger_config['threshold'])
    ticker = task['ticker_symbol'] if task['ticker_symbol'] else None
    
    current_value = _get_condition_value(condition_type, ticker, task['telegram_user_id'])
    if current_value is None:
        return False
    
    if comparison == 'above':
        return current_value > threshold
    elif comparison == 'below':
        return current_value < threshold
    return False

def _get_condition_value(condition_type: str, ticker: str, telegram_user_id: int) -> float | None:
    """Get the current value for a conditional task check."""
    try:
        user_service = UserService()
        user, _ = user_service.get_user(telegram_user_id)

        alpaca_api = AlpacaAPI(
            api_key=user['alpaca_api_key'],
            secret_key=user['alpaca_secret_key']
        )

        if condition_type == 'price':
            success, data = YFinanceAPI.quote(ticker)
            if success:
                return float(data.get('close', 0))
        
        elif condition_type == 'cash':
            success, data = alpaca_api.get_account()
            if success:
                return float(data.get('cash', 0))
        
        elif condition_type == 'portfolio_value':
            success, data = alpaca_api.get_account()
            if success:
                return float(data.get('equity', 0))
        
        elif condition_type == 'position_value':
            success, data = alpaca_api.get_position_by_symbol(ticker)
            if success:
                return float(data.get('market_value', 0))
        
        elif condition_type == 'position_pnl':
            success, data = alpaca_api.get_position_by_symbol(ticker)
            if success:
                return float(data.get('unrealized_plpc', 0))
        
        elif condition_type == 'position_allocation':
            pos_success, pos_data = alpaca_api.get_position_by_symbol(ticker)
            acc_success, acc_data = alpaca_api.get_account()
            if pos_success and acc_success:
                market_value = float(pos_data.get('market_value', 0))
                equity = float(acc_data.get('equity', 1))
                return market_value / equity if equity > 0 else 0
        
        return None
    except Exception:
        return None

async def _execute_task(task, send_message_callback, min_credits_to_run: float, queued_task_ids: set, config: dict = None):
    """Execute a triggered task - notify and run the agent."""
    task_id = task['task_id']
    ticker = task['ticker_symbol'] if task['ticker_symbol'] else None
    description = task['description']
    trigger_type = task['trigger_type']
    telegram_user_id = task['telegram_user_id']
    
    logger.info(f"Task triggered for user {telegram_user_id}: ID={task_id}, Type={trigger_type}, Ticker={ticker or 'None'}")
    
    # Build trigger message
    trigger_message = f"🔔 **{trigger_type.replace('_', ' ').title()} Task**"
    if ticker:
        trigger_message += f" ({ticker})"
    trigger_message += f"\n\n**Description:**\n{description}"

    # Check credits before running
    user_service = UserService()
    has_enough_credits, message = user_service.has_enough_credits(task['openrouter_api_key'], min_credits_to_run)
    if not has_enough_credits:
        logger.warning(f"Task {task_id} for user {telegram_user_id} skipped: insufficient credits")
        queued_task_ids.discard(task_id)  # Allow re-queuing next cycle
        await send_message_callback(trigger_message + "\n\n**Couldn't run:**\n" + message, telegram_user_id)
        return
    
    await send_message_callback(trigger_message, task['telegram_user_id'])
    
    # Build context for the agent
    context_msg = f"Automated Task Triggered\nType: {trigger_type}"
    
    if ticker:
        context_msg += f"\nTicker: {ticker}"
    
    context_msg += f"\nDescription: {description}"
    
    if trigger_type == 'conditional':
        trigger_config = json.loads(task['trigger_config'])
        context_msg += f"\nCondition Met: {trigger_config['type']} went {trigger_config['comparison']} {trigger_config['threshold']}"

    agent = InvestiAgent(
        config=config,
        user_id=task['telegram_user_id'],
        alpaca_api_key=task['alpaca_api_key'],
        alpaca_secret_key=task['alpaca_secret_key'],
        openrouter_api_key=task['openrouter_api_key'],
    )

    result = await agent.run(context_msg)
    await send_message_callback(result, telegram_user_id)
    
    # Mark task completed after successful execution
    _mark_task_completed(task)
    queued_task_ids.discard(task_id)
    logger.info(f"Task {task_id} completed for user {telegram_user_id}")

def _mark_task_completed(task):
    """Update task in DB after successful execution."""
    task_id = task['task_id']
    trigger_type = task['trigger_type']
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if trigger_type == 'one_time':
            cursor.execute("UPDATE tasks SET is_active = 0 WHERE task_id = ?", (task_id,))
        
        elif trigger_type == 'conditional':
            cursor.execute("UPDATE tasks SET is_active = 0 WHERE task_id = ?", (task_id,))
        
        elif trigger_type == 'recurring':
            task_dt = datetime.strptime(task['task_datetime'], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
            trigger_config = json.loads(task['trigger_config'])
            
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
                end_dt = datetime.strptime(trigger_config['end_value'], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
                if next_dt > end_dt:
                    cursor.execute("UPDATE tasks SET is_active = 0 WHERE task_id = ?", (task_id,))
                else:
                    cursor.execute("UPDATE tasks SET task_datetime = ? WHERE task_id = ?", (next_dt.strftime("%Y-%m-%d %H:%M:%S %Z"), task_id))
            elif trigger_config['end_type'] == 'after':
                remaining = int(trigger_config['end_value']) - 1
                if remaining <= 0:
                    cursor.execute("UPDATE tasks SET is_active = 0 WHERE task_id = ?", (task_id,))
                else:
                    trigger_config['end_value'] = remaining
                    cursor.execute("UPDATE tasks SET trigger_config = ?, task_datetime = ? WHERE task_id = ?", (json.dumps(trigger_config), next_dt.strftime("%Y-%m-%d %H:%M:%S %Z"), task_id))
