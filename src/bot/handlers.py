import traceback
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from src.agent import InvestiAgent
from src.services.user_service import UserService
from src.utils import send_markdown_message

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, config: dict):
    """Handle incoming user messages."""
    asyncio.create_task(_process_message(update, context, config))

async def _process_message(update: Update, context: ContextTypes.DEFAULT_TYPE, config: dict):
    """Process message in background."""
    min_credits_to_run = config['credits']['min_credits_to_run']

    text = update.message.text
    
    user_service = UserService()
    telegram_user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "Unknown"
    
    logger.info(f"User request from {username} (ID: {telegram_user_id}): {text[:100]}{'...' if len(text) > 100 else ''}")
    
    user, message = user_service.get_user(telegram_user_id)
    if user is None:
        logger.warning(f"User {telegram_user_id} not found in database")
        await send_markdown_message(context.bot, update.effective_chat.id, message)
        return
    
    has_enough_credits, message = user_service.has_enough_credits(user['openrouter_api_key'], min_credits_to_run)
    if not has_enough_credits:
        logger.warning(f"User {telegram_user_id} has insufficient credits")
        await send_markdown_message(context.bot, update.effective_chat.id, message)
        return
    
    await send_markdown_message(context.bot, update.effective_chat.id, "_Working on it..._")

    # Process message with agent
    agent = InvestiAgent(
        config=config,
        user_id=telegram_user_id,
        openrouter_api_key=user['openrouter_api_key'],
        alpaca_api_key=user['alpaca_api_key'],
        alpaca_secret_key=user['alpaca_secret_key']
    )
    result = await agent.run(text)
    
    logger.info(f"Completed request for user {telegram_user_id}")

    # Send with proper markdown formatting and chunking
    await send_markdown_message(context.bot, update.effective_chat.id, result)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error: {context.error}")
    logger.error(traceback.format_exc())

