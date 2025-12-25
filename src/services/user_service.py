import json
import asyncio
from datetime import datetime, timezone
from src.api.alpaca import AlpacaAPI
from src.api.openrouter import OpenRouterAPI
from src.services.database import get_async_db_connection
from src.utils import format_timestamp, format_ticker_links_async


class UserService:
    """Service for managing user data and credentials."""
    
    async def user_exists(self, telegram_user_id: int) -> tuple[bool, str]:
        """Check if a user exists."""
        async with get_async_db_connection() as conn:
            result = await conn.fetchval(
                "SELECT 1 FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )
            if result is not None:
                return True, "User already exists"
            else:
                return False, "Please use /start to register first"
    
    def validate_alpaca_credentials(self, api_key: str, secret_key: str) -> tuple[bool, str]:
        """Validate Alpaca API credentials."""
        is_valid, _ = AlpacaAPI.validate_keys(api_key, secret_key)
        if not is_valid:
            return False, "Alpaca API credentials are not valid"
        return True, "Alpaca credentials are valid"

    def validate_openrouter_credentials(self, api_key: str) -> tuple[bool, str]:
        """Validate OpenRouter API credentials."""
        is_valid = OpenRouterAPI.validate_key(api_key)
        if not is_valid:
            return False, "OpenRouter API credentials are not valid"
        return True, "OpenRouter credentials are valid"

    def has_enough_credits(self, api_key: str, min_credits: float) -> tuple[bool, str]:
        """Check if user has enough OpenRouter credits."""
        openrouter_api = OpenRouterAPI(api_key)
        success, response = openrouter_api.get_remaining_credits()
        if success:
            remaining = response.get('remaining_credits', 0)
            if remaining >= min_credits:
                return True, f"You have enough credits"
            else:
                return False, (
                    f"⚠️ *Insufficient Credits*\n\n"
                    f"You have *${remaining:.2f}* remaining.\n"
                    f"You need at least *${min_credits:.0f}* to run.\n\n"
                    f"[Top up your OpenRouter credits](https://openrouter.ai/settings/credits)"
                )
        return False, (
            f"⚠️ *Insufficient Credits*\n\n"
            f"You need at least *${min_credits:.0f}* to run.\n\n"
            f"[Top up your OpenRouter credits](https://openrouter.ai/settings/credits)"
        )

    async def register_user(self, telegram_user_id: int, telegram_username: str = None) -> tuple[bool, str]:
        """Register a new user."""
        is_exists, message = await self.user_exists(telegram_user_id)
        if is_exists:
            return False, message
        
        async with get_async_db_connection() as conn:
            await conn.execute(
                """INSERT INTO users (telegram_user_id, telegram_username, created_at) 
                   VALUES ($1, $2, $3)""",
                telegram_user_id, telegram_username, datetime.now(timezone.utc)
            )
            message = (
                "*Welcome to Investi!*\n\n"
                "*Step 1: Create Your Accounts*\n"
                "- *Alpaca* - Brokerage platform; [Sign up here](https://app.alpaca.markets/signup)."
                " _Strongly recommend using a paper trading account unless you enjoy living on the edge._\n"
                "- *OpenRouter* - AI API provider; [Sign up here](https://openrouter.ai/).\n\n"
                "*Step 2: Set Your API Credentials*\n"
                "Once you have your accounts, connect them:\n"
                "- *Alpaca credentials:* /set_alpaca\n"
                "- *OpenRouter API key:* /set_openrouter\n\n"
                "*Step 3: Set Your Operating Framework* with: /set_operating_framework\n"
                "Define the principles that guide your trading decisions. This helps me understand your risk tolerance, strategy preferences, and goals.\n\n"
                "_Example framework:_\n"
                "```\n"
                "- Never risk more than 2% per trade\n"
                "- Focus on tech stocks with strong fundamentals\n"
                "- Hold positions for 3-6 months minimum\n"
                "```\n\n"
                "Complete these steps and you'll be all set. After that just send a message and I'll get to work!"
            )
        return True, message
    
    async def set_alpaca_credentials(self, telegram_user_id: int, api_key: str, secret_key: str) -> tuple[bool, str]:
        """
        Set Alpaca credentials for a user.
        Returns (success, message).
        """
        try:
            async with get_async_db_connection() as conn:
                await conn.execute(
                    """UPDATE users 
                    SET alpaca_api_key = $1, alpaca_secret_key = $2
                    WHERE telegram_user_id = $3""",
                    api_key, secret_key, telegram_user_id
                )
            return True, "Alpaca credentials saved successfully"
        except:
            return False, "Error saving Alpaca credentials"
    
    async def set_openrouter_credentials(self, telegram_user_id: int, api_key: str) -> tuple[bool, str]:
        """
        Set OpenRouter API key for a user.
        Returns (success, message).
        """
        try:
            async with get_async_db_connection() as conn:
                await conn.execute(
                    """UPDATE users 
                    SET openrouter_api_key = $1
                    WHERE telegram_user_id = $2""",
                    api_key.strip(), telegram_user_id
                )
            return True, "OpenRouter API key saved successfully"
        except:
            return False, "Error saving OpenRouter API key"
    
    async def set_operating_framework(self, telegram_user_id: int, framework_text: str) -> tuple[bool, str]:
        """
        Set operating framework for a user.
        Returns (success, message).
        """
        try:
            async with get_async_db_connection() as conn:
                await conn.execute(
                    """UPDATE users 
                    SET operating_framework = $1
                    WHERE telegram_user_id = $2""",
                    framework_text.strip(), telegram_user_id
                )
            return True, "Operating framework saved successfully"
        except:
            return False, "Error saving operating framework"
    
    async def get_user(self, telegram_user_id: int) -> tuple[dict, str]:
        """
        Check if user has all required credentials set.
        Returns (is_valid, error_message).
        """
        exists, message = await self.user_exists(telegram_user_id)

        if not exists:
            return None, message
        
        async with get_async_db_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )
            user = dict(row)

        is_alpaca_valid, _ = await asyncio.to_thread(
            self.validate_alpaca_credentials, user['alpaca_api_key'], user['alpaca_secret_key']
        )
        is_openrouter_valid, _ = await asyncio.to_thread(
            self.validate_openrouter_credentials, user['openrouter_api_key']
        )

        if not is_alpaca_valid or not is_openrouter_valid:
            message = (
                "To get started, please provide:\n\n" +
                ("• *Alpaca API credentials* using:\n" +
                 "  /set_alpaca\n\n" if not is_alpaca_valid else "") +
                ("• *OpenRouter API key* using:\n" +
                 "  /set_openrouter\n\n" if not is_openrouter_valid else "")
            )
            return None, message

        return user, "All credentials are valid"

    async def get_status(self, telegram_user_id: int) -> str:
        """Get the status of the user's account, positions, orders, and API usage."""
        user, message = await self.get_user(telegram_user_id)
        if user is None:
            return message

        # Initialize APIs with user credentials
        alpaca_api = AlpacaAPI(
            api_key=user['alpaca_api_key'],
            secret_key=user['alpaca_secret_key']
        )
        openrouter_api = OpenRouterAPI(api_key=user['openrouter_api_key'])
        
        # Run all API calls in parallel with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    asyncio.to_thread(alpaca_api.get_account),
                    asyncio.to_thread(alpaca_api.get_orders),
                    asyncio.to_thread(alpaca_api.get_all_positions),
                    asyncio.to_thread(openrouter_api.get_key_details),
                    return_exceptions=True
                ),
                timeout=10.0
            )
            
            # Unpack results
            account_result = results[0] if not isinstance(results[0], Exception) else (False, {})
            orders_result = results[1] if not isinstance(results[1], Exception) else (False, [])
            positions_result = results[2] if not isinstance(results[2], Exception) else (False, [])
            key_details_result = results[3] if not isinstance(results[3], Exception) else (False, {})
            
            account_success, account_response = account_result
            orders_success, orders_response = orders_result
            positions_success, positions_response = positions_result
            key_details_success, key_details_response = key_details_result
            
        except asyncio.TimeoutError:
            return "_Request timed out. Please try again._"

        status_lines = []
        
        # Account Summary
        if account_success:
            acc = account_response
            status_lines.append("*Account*")
            status_lines.append(f"• Portfolio Value: `${float(acc['portfolio_value']):,.2f}`")
            status_lines.append(f"• Cash: `${float(acc['cash']):,.2f}`")
        
        # Positions
        status_lines.append("\n*Positions*")
        if positions_success and positions_response:
            # Batch format all ticker links
            symbols = [pos['symbol'] for pos in positions_response]
            symbol_links = await format_ticker_links_async(symbols)
            
            total_pl = 0
            total_cost_basis = 0
            for pos in positions_response:
                pl = float(pos['unrealized_pl'])
                plpc = float(pos['unrealized_plpc']) * 100
                total_pl += pl
                total_cost_basis += float(pos['cost_basis'])
                
                pl_sign = "+" if pl >= 0 else ""
                side_label = "Long" if pos['side'] == 'long' else "Short"
                
                symbol_link = symbol_links[pos['symbol']]
                status_lines.append(
                    f"• {symbol_link} _({side_label})_\n"
                    f"  `{float(pos['qty']):,.2f}` shares @ `${float(pos['avg_entry_price']):.2f}` → `${float(pos['current_price']):.2f}`\n"
                    f"  P/L: `{pl_sign}${pl:.2f}` _({pl_sign}{plpc:.2f}%)_"
                )
            
            # Total P/L
            total_plpc = (total_pl / total_cost_basis * 100) if total_cost_basis > 0 else 0
            total_sign = "+" if total_pl >= 0 else ""
            status_lines.append(f"\n  *Total P/L*: `{total_sign}${total_pl:.2f}` _({total_sign}{total_plpc:.2f}%)_")
        else:
            status_lines.append("_No open positions_")
        
        # Orders
        status_lines.append("\n*Orders*")
        if orders_success and orders_response:
            # Batch format all ticker links
            symbols = [order['symbol'] for order in orders_response]
            symbol_links = await format_ticker_links_async(symbols)
            
            for order in orders_response:
                side_label = "Buy" if order['side'] == 'buy' else "Sell"
                order_type = order['order_type'].capitalize()
                
                price_info = ""
                if order['limit_price']:
                    price_info = f" @ `${float(order['limit_price']):.2f}`"
                elif order['stop_price']:
                    price_info = f" @ `${float(order['stop_price']):.2f}`"
                
                filled_info = ""
                if order['filled_qty'] and order['filled_qty'] != '0':
                    filled_info = f" • _{order['filled_qty']}/{order['qty']} filled_"
                
                status_display = order['status'].capitalize()
                
                symbol_link = symbol_links[order['symbol']]
                status_lines.append(
                    f"• {symbol_link} {side_label} `{order['qty']}`\n"
                    f"  {order_type}{price_info} • {status_display}{filled_info}"
                )
        else:
            status_lines.append("_No pending orders_")
        
        # OpenRouter Usage
        status_lines.append("\n*OpenRouter Usage*")
        if key_details_success:
            data = key_details_response.get('data', {})
            status_lines.append(
                f"• Monthly: `${data.get('usage_monthly', 0):.2f}` (Total `${data.get('usage', 0):.2f}`)"
            )
        
        return "\n".join(status_lines)
    
    async def get_tasks(self, telegram_user_id: int) -> str:
        """Get all tasks and alerts for the user."""
        user, message = await self.get_user(telegram_user_id)
        if user is None:
            return message
        
        async with get_async_db_connection() as conn:
            one_time = await conn.fetch(
                """SELECT description, task_datetime, ticker_symbol 
                   FROM tasks 
                   WHERE telegram_user_id = $1 AND is_active = TRUE 
                   AND trigger_type = 'one_time'
                   ORDER BY task_datetime""",
                telegram_user_id
            )
            
            recurring = await conn.fetch(
                """SELECT description, task_datetime, ticker_symbol, trigger_config
                   FROM tasks 
                   WHERE telegram_user_id = $1 AND is_active = TRUE 
                   AND trigger_type = 'recurring'
                   ORDER BY task_datetime""",
                telegram_user_id
            )
            
            alerts = await conn.fetch(
                """SELECT description, ticker_symbol, trigger_config 
                   FROM tasks 
                   WHERE telegram_user_id = $1 AND is_active = TRUE AND trigger_type = 'conditional'
                   ORDER BY created_at""",
                telegram_user_id
            )
        
        lines = []
        
        # Batch format all ticker links
        all_symbols = []
        for task in one_time:
            if task['ticker_symbol']:
                all_symbols.append(task['ticker_symbol'])
        for task in recurring:
            if task['ticker_symbol']:
                all_symbols.append(task['ticker_symbol'])
        for alert in alerts:
            if alert['ticker_symbol']:
                all_symbols.append(alert['ticker_symbol'])
        
        symbol_links = await format_ticker_links_async(all_symbols) if all_symbols else {}
        
        # One Time Tasks
        lines.append("*One Time Tasks*")
        if one_time:
            for task in one_time:
                ticker = symbol_links.get(task['ticker_symbol'], '') + " " if task['ticker_symbol'] else ""
                desc = task['description'][:60] + "..." if len(task['description']) > 60 else task['description']
                task_time = format_timestamp(task['task_datetime'])
                lines.append(f"• {ticker}_{desc}_\n  `{task_time}`")
        else:
            lines.append("_None_")
        
        # Recurring Tasks
        lines.append("\n*Recurring Tasks*")
        if recurring:
            for task in recurring:
                ticker = symbol_links.get(task['ticker_symbol'], '') + " " if task['ticker_symbol'] else ""
                desc = task['description'][:60] + "..." if len(task['description']) > 60 else task['description']
                task_time = format_timestamp(task['task_datetime'])
                
                # Parse recurrence details
                config = json.loads(task['trigger_config']) if isinstance(task['trigger_config'], str) else task['trigger_config']
                recurrence_type = config['type']
                interval = config['interval']
                
                # Format recurrence string
                if interval == 1:
                    recurrence = f"every {recurrence_type}"
                else:
                    recurrence = f"every {interval} {recurrence_type}s"
                
                # Add end condition if applicable
                if config['end_type'] == 'on':
                    end_value = config['end_value']
                    # Handle both datetime objects and ISO strings from JSONB
                    if isinstance(end_value, str):
                        end_value = datetime.fromisoformat(end_value.replace('Z', '+00:00'))
                    end_date = format_timestamp(end_value)
                    recurrence += f" until {end_date}"
                elif config['end_type'] == 'after':
                    remaining = config['end_value']
                    recurrence += f" ({remaining} time{'s' if remaining != 1 else ''} remaining)"
                
                lines.append(f"• {ticker}_{desc}_\n  `Next: {task_time}`\n  `{recurrence}`")
        else:
            lines.append("_None_")
        
        # Alerts
        lines.append("\n*Alerts*")
        if alerts:
            for alert in alerts:
                config = json.loads(alert['trigger_config']) if isinstance(alert['trigger_config'], str) else alert['trigger_config']
                ticker = symbol_links.get(alert['ticker_symbol'], '') + " " if alert['ticker_symbol'] else ""
                
                condition_type = config['type'].replace('_', ' ').title()
                comparison = config['comparison'].title()
                threshold = config['threshold']
                
                if config['type'] in ['position_allocation', 'position_pnl']:
                    threshold_str = f"{threshold * 100:.1f}%"
                else:
                    threshold_str = f"${threshold:,.2f}"
                
                lines.append(f"• {ticker}`{condition_type} {comparison} {threshold_str}`")
        else:
            lines.append("_None_")
        
        return "\n".join(lines)
    
    async def get_watchlists(self, telegram_user_id: int) -> str:
        """Get all watchlists for the user."""
        user, message = await self.get_user(telegram_user_id)
        if user is None:
            return message
        
        async with get_async_db_connection() as conn:
            rows = await conn.fetch(
                "SELECT watchlist_name, assets FROM watchlists WHERE telegram_user_id = $1",
                telegram_user_id
            )
            watchlists = [dict(row) for row in rows]
        
        lines = ["*Watchlists*"]
        if watchlists:
            # Batch format all ticker links
            all_symbols = []
            for wl in watchlists:
                assets = wl['assets'] if isinstance(wl['assets'], list) else json.loads(wl['assets'])
                all_symbols.extend(assets)
            
            symbol_links = await format_ticker_links_async(all_symbols) if all_symbols else {}
            
            for wl in watchlists:
                assets = wl['assets'] if isinstance(wl['assets'], list) else json.loads(wl['assets'])
                asset_count = len(assets)
                asset_links = [symbol_links[asset] for asset in assets]
                lines.append(f"• *{wl['watchlist_name']}*: `{asset_count}` assets ({', '.join(asset_links)})")
        else:
            lines.append("_No watchlists_")
        
        return "\n".join(lines)
    
    async def delete_account(self, telegram_user_id: int) -> tuple[bool, str]:
        """
        Delete a user account and all associated data.
        Returns (success, message).
        """
        exists, message = await self.user_exists(telegram_user_id)
        if not exists:
            return False, message
        
        try:
            async with get_async_db_connection() as conn:
                # First, get all note_ids for this user to delete embeddings
                note_ids = await conn.fetch(
                    "SELECT note_id FROM notes WHERE telegram_user_id = $1",
                    telegram_user_id
                )
                note_id_list = [row['note_id'] for row in note_ids]
                
                # Delete note embeddings
                if note_id_list:
                    await conn.execute(
                        "DELETE FROM note_embeddings WHERE note_id = ANY($1)",
                        note_id_list
                    )
                
                # Delete tasks
                await conn.execute(
                    "DELETE FROM tasks WHERE telegram_user_id = $1",
                    telegram_user_id
                )
                
                # Delete notes
                await conn.execute(
                    "DELETE FROM notes WHERE telegram_user_id = $1",
                    telegram_user_id
                )
                
                # Delete watchlists
                await conn.execute(
                    "DELETE FROM watchlists WHERE telegram_user_id = $1",
                    telegram_user_id
                )
                
                # Finally, delete the user
                await conn.execute(
                    "DELETE FROM users WHERE telegram_user_id = $1",
                    telegram_user_id
                )
            return True, "Account and all associated data have been deleted successfully"
        except Exception as e:
            return False, f"Error deleting account: {str(e)}"
