"""
Prompt builder module for loading and formatting role-specific system prompts.
This module consolidates prompt templates and dynamic data fetching.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from src.api.alpaca import AlpacaAPI
from src.api.yahoo_finance import YFinanceAPI
from src.services.database import get_db_connection
from src.services.user_service import UserService
from src.utils import validate_date


def get_today_utc():
    """Get current UTC datetime as formatted string."""
    return datetime.now(timezone.utc).strftime("%A %Y-%m-%d %H:%M:%S %Z")

def get_market_status():
    """
    Fetch and format market status data.
    """
    yfinance_api = YFinanceAPI()
    success, data = yfinance_api.market_status()
    if success:
        return data['message']
    else:
        return data


def get_account_data(user_id: int):
    """
    Fetch and format account data including equity, cash, buying power, risk metrics, positions, and orders.
    Args:
        user_id: Telegram user ID to fetch API credentials
    Returns: tuple (equity_str, cash_str, buying_power_str, pdt_status_str, daytrade_count_str, 
                    maintenance_margin_str, long_market_value_str, short_market_value_str, 
                    positions_str, orders_str)
    """
    user_service = UserService()
    user, _ = user_service.get_user(user_id)
    
    alpaca_api = AlpacaAPI(
        api_key=user['alpaca_api_key'],
        secret_key=user['alpaca_secret_key']
    )

    # Fetch Account Data
    account_success, account_data = alpaca_api.get_account()
    if account_success:
        equity = f"${float(account_data.get('equity', 0)):,.2f}"
        cash = f"${float(account_data.get('cash', 0)):,.2f}"
        buying_power = f"${float(account_data.get('buying_power', 0)):,.2f}"
        pdt_status = "Yes" if account_data.get('pattern_day_trader', False) else "No"
        daytrade_count = str(account_data.get('daytrade_count', 0))
        maintenance_margin = f"${float(account_data.get('maintenance_margin', 0)):,.2f}"
        long_market_value = f"${float(account_data.get('long_market_value', 0)):,.2f}"
        short_market_value = f"${float(account_data.get('short_market_value', 0)):,.2f}"
    else:
        equity = "Unable to fetch"
        cash = "Unable to fetch"
        buying_power = "Unable to fetch"
        pdt_status = "Unable to fetch"
        daytrade_count = "Unable to fetch"
        maintenance_margin = "Unable to fetch"
        long_market_value = "Unable to fetch"
        short_market_value = "Unable to fetch"
    
    # Fetch Positions
    positions_success, positions_data = alpaca_api.get_all_positions()
    if positions_success and positions_data:
        positions_lines = []
        total_pl = 0
        for pos in positions_data:
            symbol = pos.get('symbol', 'N/A')
            qty = float(pos.get('qty', 0))
            current_price = float(pos.get('current_price', 0))
            market_value = float(pos.get('market_value', 0))
            unrealized_pl = float(pos.get('unrealized_pl', 0))
            unrealized_plpc = float(pos.get('unrealized_plpc', 0)) * 100
            side = pos.get('side', 'long')
            sign = "+" if unrealized_pl >= 0 else ""
            total_pl += unrealized_pl
            positions_lines.append(
                f"  {symbol}: {qty:.2f} shares @ ${current_price:.2f} | Value: ${market_value:,.2f} | P&L: {sign}${unrealized_pl:,.2f} ({sign}{unrealized_plpc:.2f}%) | {side}"
            )
        total_sign = "+" if total_pl >= 0 else ""
        positions_str = "\n".join(positions_lines) + f"\n\n  TOTAL P&L: {total_sign}${total_pl:,.2f}"
    else:
        positions_str = "  No open positions"

    # Fetch Open Orders
    orders_success, orders_data = alpaca_api.get_orders(status="open")
    if orders_success and orders_data:
        orders_lines = []
        for order in orders_data:
            symbol = order.get('symbol', 'N/A')
            side = order.get('side', 'N/A').upper()
            order_type = order.get('type', 'N/A')
            status = order.get('status', 'N/A')
            
            # Format timestamps
            submitted_raw = order.get('submitted_at', '').replace('Z', '')
            _, submitted_at = validate_date(
                submitted_raw,
                "%Y-%m-%dT%H:%M:%S.%f" if '.' in submitted_raw else "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S %Z",
                timezone.utc
            )
            submitted_at = submitted_at or "N/A"
            
            expires_raw = order.get('expires_at', '').replace('Z', '')
            _, expires_at = validate_date(
                expires_raw,
                "%Y-%m-%dT%H:%M:%S.%f" if '.' in expires_raw else "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S %Z",
                timezone.utc
            )
            expires_at = expires_at or "N/A"
            
            # Handle qty vs notional
            qty = order.get('qty')
            notional = order.get('notional')
            if qty:
                qty_str = f"{qty} shares"
            elif notional:
                qty_str = f"${notional}"
            else:
                qty_str = "N/A"
                
            orders_lines.append(f"  {symbol} | {order_type} | {side} | {qty_str} | {status} | Submitted: {submitted_at} | Expires: {expires_at}")
        orders_str = "\n".join(orders_lines) if orders_lines else "  No open orders"
    else:
        orders_str = "  No open orders"

    return equity, cash, buying_power, pdt_status, daytrade_count, maintenance_margin, long_market_value, short_market_value, positions_str, orders_str


def get_upcoming_tasks(user_id: int):
    """
    Fetch and format upcoming active tasks for a user.
    Returns: formatted string of tasks
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM tasks 
               WHERE telegram_user_id = ? AND is_active = 1 
               ORDER BY task_datetime NULLS LAST""",
            (user_id,)
        )
        active_tasks = [dict(row) for row in cursor.fetchall()]
    
    if not active_tasks:
        return "  No upcoming tasks"
    
    lines = []
    for task in active_tasks:
        task_id = task['task_id']  # Full UUID
        trigger_type = task['trigger_type']
        role = task['role']
        ticker = task['ticker_symbol'] or "none"
        
        # Format date/trigger consistently
        if trigger_type == "conditional":
            date_str = "conditional"
        elif task['task_datetime']:
            date_str = task['task_datetime'][:16]  # YYYY-MM-DD HH:MM
        else:
            date_str = "N/A"
        
        # Truncate description to 45 chars for better formatting
        desc = task['description'][:45] + "..." if len(task['description']) > 45 else task['description']
        
        # Parse related IDs (stored as JSON arrays) - show FULL UUIDs
        related_notes = json.loads(task['related_note_ids']) if task['related_note_ids'] else []
        related_tasks = json.loads(task['related_task_ids']) if task['related_task_ids'] else []
        related_watchlists = json.loads(task['related_watchlist_ids']) if task['related_watchlist_ids'] else []
        
        # Format related IDs for display (show full UUIDs)
        notes_str = ", ".join(related_notes) if related_notes else "none"
        tasks_str = ", ".join(related_tasks) if related_tasks else "none"
        watchlists_str = ", ".join(related_watchlists) if related_watchlists else "none"
        
        lines.append(
            f"  {task_id} | {date_str:16} | {role:18} | {trigger_type:12} | {desc}\n"
            f"    Related Ticker Symbol: {ticker}\n"
            f"    Related Note IDs: {notes_str}\n"
            f"    Related Task IDs: {tasks_str}\n"
            f"    Related Watchlist IDs: {watchlists_str}"
        )
    
    return "\n".join(lines)


def get_watchlist_data(user_id: int):
    """
    Fetch and format watchlist data for a user.
    Returns: formatted string of watchlists
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM watchlists WHERE telegram_user_id = ? ORDER BY created_at",
            (user_id,)
        )
        watchlists = [dict(row) for row in cursor.fetchall()]
    
    if not watchlists:
        return "  No watchlists"
    
    lines = []
    for wl in watchlists:
        wl_id = wl['watchlist_id']  # Full UUID
        name = wl['watchlist_name']
        assets = json.loads(wl['assets']) if wl['assets'] else []
        assets_str = ", ".join(assets) if assets else "none"
        lines.append(f"  {wl_id} | {name} | {assets_str}")
    
    return "\n".join(lines)


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


def build_prompt(role: str, user_id: int) -> str:
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
    
    # Gather dynamic data
    today = get_today_utc()
    market_status = get_market_status()
    equity, cash, buying_power, pdt_status, daytrade_count, maintenance_margin, long_market_value, short_market_value, positions, orders = get_account_data(user_id)
    tasks = get_upcoming_tasks(user_id)
    watchlists = get_watchlist_data(user_id)
    
    # Format the template with dynamic data
    formatted_prompt = template.format(
        today=today,
        market_status=market_status,
        equity=equity,
        cash=cash,
        buying_power=buying_power,
        pdt_status=pdt_status,
        daytrade_count=daytrade_count,
        maintenance_margin=maintenance_margin,
        long_market_value=long_market_value,
        short_market_value=short_market_value,
        positions=positions,
        orders=orders,
        tasks=tasks,
        watchlists=watchlists
    )
    
    return formatted_prompt


# Convenience functions for each role
def get_portfolio_manager_prompt(user_id: int) -> str:
    """Get the formatted portfolio manager system prompt."""
    return build_prompt('portfolio_manager', user_id)


def get_analyst_prompt(user_id: int) -> str:
    """Get the formatted analyst system prompt."""
    return build_prompt('analyst', user_id)


def get_trader_prompt(user_id: int) -> str:
    """Get the formatted trader system prompt."""
    return build_prompt('trader', user_id)


def get_technical_analyst_prompt() -> str:
    """Get the formatted technical analyst system prompt."""
    return load_prompt_template('technical_analyst')


def get_guardrail_prompt() -> str:
    """Get the guardrail prompt (no dynamic data needed)."""
    return load_prompt_template('guardrail')

