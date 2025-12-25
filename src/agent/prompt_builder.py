import json
from pathlib import Path
from datetime import datetime, timezone
from src.api.alpaca import AlpacaAPI
from src.services.database import get_async_db_connection
from src.services.user_service import UserService
from src.utils import format_timestamp
import exchange_calendars as xcals


def get_current_time_utc():
    """Get current UTC datetime as formatted string."""
    now = datetime.now(timezone.utc)
    timestamp_str = now.strftime("%A, %d %B %Y, %H:%M:%S %Z")
    return timestamp_str

def get_market_info():
    """
    Fetch market information for all major exchanges.
    Returns: JSON string of market information
    """
    # More markets can be added here
    # See: https://github.com/gerrymanoim/exchange_calendars/blob/master/README.md
    MARKETS = {
        "XNYS": "New York Stock Exchange",
        "XTSE": "Toronto Stock Exchange",
        # "BVMF": "BMF Bovespa",
        "XLON": "London Stock Exchange",
        "XPAR": "Euronext Paris",
        "XFRA": "Frankfurt Stock Exchange",
        "XSWX": "SIX Swiss Exchange",
        # "XTKS": "Tokyo Stock Exchange",
        # "XHKG": "Hong Kong Stock Exchange",
        # "XSHG": "Shanghai Stock Exchange",
        # "XASX": "Australian Securities Exchange",
        # "XSES": "Singapore Exchange",
        # "XBOM": "Bombay Stock Exchange"
    } 
    now = datetime.now(timezone.utc)
    
    market_info = []
    for code, name in MARKETS.items():
        cal = xcals.get_calendar(code)
        is_open = cal.is_open_on_minute(now)
        
        market_data = {
            "name": name,
            "is_open": is_open,
            "next_open": format_timestamp(cal.next_open(now)),
            "next_close": format_timestamp(cal.next_close(now))
        }
        
        market_info.append(market_data)
    
    return json.dumps(market_info, indent=2)


async def get_account_data(user_id: int):
    """
    Fetch account data including equity, cash, buying power, and risk metrics.
    Args:
        user_id: Telegram user ID to fetch API credentials
    Returns: JSON string of account data
    """
    fields = ["currency", "buying_power", "cash", "portfolio_value", "pattern_day_trader", "equity", "long_market_value", "short_market_value", "position_market_value", "daytrade_count"]

    user_service = UserService()
    user, _ = await user_service.get_user(user_id)
    
    alpaca_api = AlpacaAPI(
        api_key=user['alpaca_api_key'],
        secret_key=user['alpaca_secret_key']
    )

    account_success, account_data = alpaca_api.get_account()
    if account_success:
        return json.dumps({field: account_data[field] for field in fields}, indent=2)
    else:
        return json.dumps({"error": "Unable to fetch account data"}, indent=2)


async def get_positions_data(user_id: int):
    """
    Fetch all open positions.
    Args:
        user_id: Telegram user ID to fetch API credentials
    Returns: JSON string of positions data
    """

    fields = ["symbol", "exchange", "qty", "avg_entry_price", "side", "market_value", "unrealized_pl", "unrealized_plpc", "current_price"]
    user_service = UserService()
    user, _ = await user_service.get_user(user_id)
    
    alpaca_api = AlpacaAPI(
        api_key=user['alpaca_api_key'],
        secret_key=user['alpaca_secret_key']
    )

    positions_success, positions_data = alpaca_api.get_all_positions()
    if positions_success:
        if not positions_data:
            return "No open positions"
        filtered_positions = [
            {field: pos.get(field) for field in fields} for pos in positions_data
        ]
        return json.dumps(filtered_positions, indent=2)
    else:
        return json.dumps({"error": "Unable to fetch positions"}, indent=2)


async def get_orders_data(user_id: int):
    """
    Fetch all open orders.
    Args:
        user_id: Telegram user ID to fetch API credentials
    Returns: JSON string of orders data
    """
    fields = ["created_at", "symbol", "notional", "qty", "filled_qty", "type", "side", "time_in_force", "limit_price", "stop_price", "status", "expires_at"]
    user_service = UserService()
    user, _ = await user_service.get_user(user_id)
    
    alpaca_api = AlpacaAPI(
        api_key=user['alpaca_api_key'],
        secret_key=user['alpaca_secret_key']
    )

    orders_success, orders_data = alpaca_api.get_orders(status="open")
    if orders_success:
        if not orders_data:
            return "No open orders"
        filtered_orders = [
            {field: order.get(field) for field in fields} for order in orders_data
        ]
        return json.dumps(filtered_orders, indent=2)
    else:
        return json.dumps({"error": "Unable to fetch orders"}, indent=2)


async def get_upcoming_tasks(user_id: int):
    """
    Fetch and format upcoming active tasks for a user.
    Returns: JSON string of tasks
    """
    fields = ["task_id", "created_at", "ticker_symbol", "role", "description", "task_datetime", "trigger_type", "trigger_config", "related_note_ids", "related_task_ids", "related_watchlist_ids"]
    async with get_async_db_connection() as conn:
        rows = await conn.fetch(
            """SELECT * FROM tasks 
               WHERE telegram_user_id = $1 AND is_active = TRUE 
               ORDER BY task_datetime NULLS LAST""",
            user_id
        )
        active_tasks = [dict(row) for row in rows]
    
    if not active_tasks:
        return "No upcoming tasks"
    
    # Format timestamps - JSONB fields are already dicts/lists from asyncpg
    for task in active_tasks:
        task['created_at'] = format_timestamp(task['created_at'])
        if task.get('task_datetime'):  # task_datetime can be NULL
            task['task_datetime'] = format_timestamp(task['task_datetime'])
    
    filtered_tasks = [
        {field: task.get(field) for field in fields} for task in active_tasks
    ]
    return json.dumps(filtered_tasks, indent=2)


async def get_watchlist_data(user_id: int):
    """
    Fetch and format watchlist data for a user.
    Returns: JSON string of watchlists
    """
    fields = ["watchlist_id", "created_at", "watchlist_name", "assets", "updated_at"]
    async with get_async_db_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM watchlists WHERE telegram_user_id = $1 ORDER BY created_at",
            user_id
        )
        watchlists = [dict(row) for row in rows]
    
    if not watchlists:
        return "No watchlists"
    
    # Convert JSONB assets back to list and format timestamps
    for wl in watchlists:
        if wl.get('assets') and not isinstance(wl['assets'], list):
            wl['assets'] = wl['assets']  # Already a list from JSONB
        wl['created_at'] = format_timestamp(wl['created_at'])
        wl['updated_at'] = format_timestamp(wl['updated_at'])
    
    filtered_watchlists = [
        {field: wl.get(field) for field in fields} for wl in watchlists
    ]
    
    return json.dumps(filtered_watchlists, indent=2)


async def get_operating_framework(user_id: int) -> str:
    """
    Fetch user's custom operating framework.
    Returns: User's operating framework text or default message
    """
    async with get_async_db_connection() as conn:
        row = await conn.fetchrow(
            "SELECT operating_framework FROM users WHERE telegram_user_id = $1",
            user_id
        )
        if row and row['operating_framework']:
            return row['operating_framework']
    return "No custom operating framework set. Operate within the best of your ability."


def load_prompt_template(role: str) -> str:
    """
    Load a prompt template from a markdown file.
    
    Args:
        role: One of 'portfolio_manager', 'analyst', or 'trader'
    
    Returns:
        String content of the prompt template
    """
    prompts_dir = Path(__file__).parent / "prompts"
    template_path = prompts_dir / f"{role}.md"
    
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")
    
    with open(template_path, 'r') as f:
        return f.read()


async def build_prompt(role: str, user_id: int) -> str:
    """
    Build a complete system prompt for a given role with dynamic data injection.
    
    Args:
        role: One of 'portfolio_manager', 'analyst', or 'trader'
        user_id: Telegram user ID to filter user-specific data
    
    Returns:
        Formatted system prompt string with all dynamic data injected
    """
    # Load the template
    template = load_prompt_template(role)
    
    # Gather dynamic data (all as JSON strings)
    current_datetime = get_current_time_utc()
    market_info = get_market_info()
    operating_framework = await get_operating_framework(user_id)
    
    # Format the template with dynamic data
    formatted_prompt = template.format(
        current_datetime=current_datetime,
        market_info=market_info,
        operating_framework=operating_framework
    )
    
    return formatted_prompt


# Convenience functions for each role
async def get_portfolio_manager_prompt(user_id: int) -> str:
    """Get the formatted portfolio manager system prompt."""
    return await build_prompt('portfolio_manager', user_id)


async def get_analyst_prompt(user_id: int) -> str:
    """Get the formatted analyst system prompt."""
    return await build_prompt('analyst', user_id)


async def get_trader_prompt(user_id: int) -> str:
    """Get the formatted trader system prompt."""
    return await build_prompt('trader', user_id)


def get_technical_analyst_prompt() -> str:
    """Get the formatted technical analyst system prompt."""
    return load_prompt_template('technical_analyst')


def get_guardrail_prompt() -> str:
    """Get the guardrail prompt (no dynamic data needed)."""
    return load_prompt_template('guardrail')


async def get_background_information(
    user_id: int,
    include_account: bool = True,
    include_positions: bool = True,
    include_orders: bool = True,
    include_tasks: bool = True,
    include_watchlists: bool = True
) -> str:
    """
    Build background information section for injection into user messages.
    
    Args:
        user_id: Telegram user ID to filter user-specific data
        include_account: Include account data (cash, equity, buying power)
        include_positions: Include open positions
        include_orders: Include open orders
        include_tasks: Include upcoming tasks
        include_watchlists: Include watchlists
    
    Returns:
        Formatted background information string
    """
    sections = []
    
    if include_account:
        account_data = await get_account_data(user_id)
        sections.append(f"## Account Data:\n{account_data}")
    
    if include_positions:
        positions = await get_positions_data(user_id)
        sections.append(f"## Open Positions:\n{positions}")
    
    if include_orders:
        orders = await get_orders_data(user_id)
        sections.append(f"## Open Orders:\n{orders}")
    
    if include_tasks:
        tasks = await get_upcoming_tasks(user_id)
        sections.append(f"## Upcoming Tasks:\n{tasks}")
    
    if include_watchlists:
        watchlists = await get_watchlist_data(user_id)
        sections.append(f"## Watchlists:\n{watchlists}")
    
    content = "\n\n".join(sections)
    return f"<background_information>\n{content}\n</background_information>"

