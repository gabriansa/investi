from datetime import datetime, timezone
from src.api.alpaca import AlpacaAPI
from src.api.openrouter import OpenRouterAPI
from src.services.database import get_db_connection


class UserService:
    """Service for managing user data and credentials."""
    
    def user_exists(self, telegram_user_id: int) -> tuple[bool, str]:
        """Check if a user exists."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM users WHERE telegram_user_id = ?",
                (telegram_user_id,)
            )
            if cursor.fetchone() is not None:
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
                return False, f"⚠️ *Insufficient Credits* - *${remaining:.2f}* remaining\nYou need at least ${min_credits:.0f} to run.\n→ [Top up OpenRouter](https://openrouter.ai/settings/credits)"
        return False, f"⚠️ *Insufficient Credits*\nYou need at least ${min_credits:.0f} to run.\n→ [Top up OpenRouter](https://openrouter.ai/settings/credits)"

    def register_user(self, telegram_user_id: int) -> tuple[bool, str]:
        """Register a new user."""
        is_exists, message = self.user_exists(telegram_user_id)
        if is_exists:
            return False, message
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO users (telegram_user_id, created_at) 
                   VALUES (?, ?)""",
                (telegram_user_id, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z"))
            )
            message = (
                "*Welcome to Investi!*\n\n"
                "To get started, please provide:\n\n"
                "• *Alpaca API credentials* using:\n"
                "  `/set_alpaca <api_key> <secret_key>`\n\n"
                "• *OpenRouter API key* using:\n"
                "  `/set_openrouter <api_key>`"
            )
        return True, message
    
    def set_alpaca_credentials(self, telegram_user_id: int, api_key: str, secret_key: str) -> tuple[bool, str]:
        """
        Set Alpaca credentials for a user.
        Returns (success, message).
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """UPDATE users 
                    SET alpaca_api_key = ?, alpaca_secret_key = ?
                    WHERE telegram_user_id = ?""",
                    (api_key, secret_key, telegram_user_id)
                )
            return True, "Alpaca credentials saved successfully"
        except:
            return False, "Error saving Alpaca credentials"
    
    def set_openrouter_credentials(self, telegram_user_id: int, api_key: str) -> tuple[bool, str]:
        """
        Set OpenRouter API key for a user.
        Returns (success, message).
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """UPDATE users 
                    SET openrouter_api_key = ?
                    WHERE telegram_user_id = ?""",
                    (api_key.strip(), telegram_user_id)
                )
            return True, "OpenRouter API key saved successfully"
        except:
            return False, "Error saving OpenRouter API key"
    
    def get_user(self, telegram_user_id: int) -> tuple[dict, str]:
        """
        Check if user has all required credentials set.
        Returns (is_valid, error_message).
        """
        exists, message = self.user_exists(telegram_user_id)

        if not exists:
            return None, message
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE telegram_user_id = ?",
                (telegram_user_id,)
            )
            row = cursor.fetchone()
            user = dict(row)

        is_alpaca_valid, _ = self.validate_alpaca_credentials(user['alpaca_api_key'], user['alpaca_secret_key'])
        is_openrouter_valid, _ = self.validate_openrouter_credentials(user['openrouter_api_key'])

        if not is_alpaca_valid or not is_openrouter_valid:
            message = (
                "To get started, please provide:\n\n" +
                ("• *Alpaca API credentials* using:\n" +
                 "  `/set_alpaca <api_key> <secret_key>`\n\n" if not is_alpaca_valid else "") +
                ("• *OpenRouter API key* using:\n" +
                 "  `/set_openrouter <api_key>`\n\n" if not is_openrouter_valid else "")
            )
            return None, message

        return user, "All credentials are valid"

    def get_status(self, telegram_user_id: int) -> str:
        """Get the status of the user's account, positions, orders, and API usage."""
        user, message = self.get_user(telegram_user_id)
        if user is None:
            return message

        # Initialize APIs with user credentials
        alpaca_api = AlpacaAPI(
            api_key=user['alpaca_api_key'],
            secret_key=user['alpaca_secret_key']
        )
        openrouter_api = OpenRouterAPI(api_key=user['openrouter_api_key'])
        
        account_success, account_response = alpaca_api.get_account()
        orders_success, orders_response = alpaca_api.get_orders()
        positions_success, positions_response = alpaca_api.get_all_positions()
        key_details_success, key_details_response = openrouter_api.get_key_details()

        status_lines = []
        
        # Account Summary
        if account_success:
            acc = account_response
            status_lines.append("*💰 Account*")
            status_lines.append(f"• Equity: `${float(acc['equity']):,.2f}`")
            status_lines.append(f"• Cash: `${float(acc['cash']):,.2f}`")
            status_lines.append(f"• Buying Power: `${float(acc['buying_power']):,.2f}`")
            status_lines.append(f"• Leverage: `{acc['multiplier']}x`")
        
        # Positions
        status_lines.append("\n*💼 Positions*")
        if positions_success and positions_response:
            total_pl = 0
            total_cost_basis = 0
            for pos in positions_response:
                pl = float(pos['unrealized_pl'])
                plpc = float(pos['unrealized_plpc']) * 100
                total_pl += pl
                total_cost_basis += float(pos['cost_basis'])
                
                pl_sign = "+" if pl >= 0 else ""
                side_label = "Long" if pos['side'] == 'long' else "Short"
                
                status_lines.append(
                    f"• *{pos['symbol']}* _({side_label})_\n"
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
        status_lines.append("\n*📋 Orders*")
        if orders_success and orders_response:
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
                
                status_lines.append(
                    f"• *{order['symbol']}* {side_label} `{order['qty']}`\n"
                    f"  {order_type}{price_info} • {status_display}{filled_info}"
                )
        else:
            status_lines.append("_No pending orders_")
        
        # API Usage
        status_lines.append("\n*💳 API Usage*")
        if key_details_success:
            data = key_details_response.get('data', {})
            status_lines.append(
                f"• Total: `${data.get('usage', 0):.2f}`\n"
                f"• Monthly: `${data.get('usage_monthly', 0):.2f}`"
            )
        
        return "\n".join(status_lines)
    
    def delete_account(self, telegram_user_id: int) -> tuple[bool, str]:
        """
        Delete a user account and all associated data.
        Returns (success, message).
        """
        exists, message = self.user_exists(telegram_user_id)
        if not exists:
            return False, message
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                # Delete all notes for this user
                cursor.execute(
                    "DELETE FROM notes WHERE telegram_user_id = ?",
                    (telegram_user_id,)
                )
                # Delete all tasks for this user
                cursor.execute(
                    "DELETE FROM tasks WHERE telegram_user_id = ?",
                    (telegram_user_id,)
                )
                # Delete all watchlists for this user
                cursor.execute(
                    "DELETE FROM watchlists WHERE telegram_user_id = ?",
                    (telegram_user_id,)
                )
                # Delete the user
                cursor.execute(
                    "DELETE FROM users WHERE telegram_user_id = ?",
                    (telegram_user_id,)
                )
            return True, "Account and all associated data have been deleted successfully"
        except Exception as e:
            return False, f"Error deleting account: {str(e)}"