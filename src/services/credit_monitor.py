import asyncio
import logging
from src.api.openrouter import OpenRouterAPI
from src.services.database import get_async_db_connection

logger = logging.getLogger(__name__)


async def check_credits(send_message_callback, config: dict):
    min_credits_warning = config['credits']['min_credits_warning']
    credit_check_interval_hours = config['credits']['credit_check_interval_hours']

    while True:
        try:
            async with get_async_db_connection() as conn:
                users = await conn.fetch(
                    "SELECT telegram_user_id, openrouter_api_key FROM users WHERE openrouter_api_key IS NOT NULL"
                )
            
            for user in users:
                openrouter_api = OpenRouterAPI(user['openrouter_api_key'])
                success, response = await asyncio.to_thread(openrouter_api.get_remaining_credits)
                if success:
                    remaining = response.get('remaining_credits', 0)
                    if remaining < min_credits_warning:
                        logger.warning(f"Low credits detected for user {user['telegram_user_id']}: ${remaining:.2f}")
                        await send_message_callback(
                            message=(
                                f"⚠️ **Low Credits**\n\n"
                                f"You have **${remaining:.2f}** remaining.\n\n"
                                f"[Top up your OpenRouter credits](https://openrouter.ai/settings/credits)"
                            ),
                            user_id=user['telegram_user_id']
                        )
                        break
        except Exception as e:
            logger.error(f"Error checking credits: {e}")
        
        await asyncio.sleep(credit_check_interval_hours * 3600)
