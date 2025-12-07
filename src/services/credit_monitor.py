import asyncio
from src.api.openrouter import OpenRouterAPI
from src.services.database import get_db_connection


async def check_credits(send_message_callback, config: dict):
    min_credits_warning = config['credits']['min_credits_warning']
    credit_check_interval_hours = config['credits']['credit_check_interval_hours']

    while True:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT telegram_user_id, openrouter_api_key FROM users WHERE openrouter_api_key IS NOT NULL"
                )
                users = cursor.fetchall()
            
            for user in users:
                openrouter_api = OpenRouterAPI(user['openrouter_api_key'])
                success, response = openrouter_api.get_remaining_credits()
                if success:
                    remaining = response.get('remaining_credits', 0)
                    if remaining < min_credits_warning:
                        await send_message_callback(
                            message=f"⚠️ *Low Credits* - *${remaining:.2f}* remaining\n→ [Top up OpenRouter](https://openrouter.ai/settings/credits)",
                            user_id=user['telegram_user_id']
                        )
                        break
        except Exception as e:
            print(f"Error checking credits: {e}")
        
        await asyncio.sleep(credit_check_interval_hours * 3600)
