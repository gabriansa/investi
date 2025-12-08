from telegram.ext import Application, CommandHandler, MessageHandler, filters
import asyncio
import os
import yaml
import logging
from src.services.database import init_database
from src.services.credit_monitor import check_credits
from src.services.task_engine import check_tasks
from src.bot.commands import (
    start_command, 
    set_alpaca_command, 
    set_openrouter_command,
    status_command,
    delete_account_command,
)
from src.bot.handlers import handle_message, error_handler
from src.utils import setup_logger, send_bot_markdown_message
from dotenv import load_dotenv
from agents import set_trace_processors
from langsmith.wrappers import OpenAIAgentsTracingProcessor

load_dotenv()

# Setup logging
setup_logger()
logger = logging.getLogger(__name__)

# Setup tracing globally once
set_trace_processors([OpenAIAgentsTracingProcessor()])
logger.info("LangSmith tracing initialized")

token = os.getenv('TELEGRAM_BOT_TOKEN')

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)


async def post_init(application: Application):
    """Initialize background tasks after bot starts."""
    
    async def send_notification(message: str, user_id: int):
        """Send notification with proper markdown formatting."""
        try:
            await send_bot_markdown_message(application.bot, user_id, message)
        except Exception as e:
            logger.error(f"Error sending notification to user {user_id}: {e}")
    
    # Start task engine
    asyncio.create_task(check_tasks(
        send_notification,
        config=config
    ))
    logger.info("Task engine started")
    
    # Start credit monitoring
    asyncio.create_task(check_credits(
        send_notification,
        config=config
    ))
    logger.info("Credit monitoring started")


if __name__ == "__main__":
    logger.info("Starting bot...")
    
    # Initialize database
    init_database()
    logger.info("Database initialized")
    
    # Build application
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", lambda update, context: start_command(update)))
    app.add_handler(CommandHandler("status", lambda update, context: status_command(update)))
    app.add_handler(CommandHandler("set_alpaca", lambda update, context: set_alpaca_command(update, context)))
    app.add_handler(CommandHandler("set_openrouter", lambda update, context: set_openrouter_command(update, context)))
    app.add_handler(CommandHandler("delete_account", lambda update, context: delete_account_command(update)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: handle_message(update, config)))
    app.add_error_handler(error_handler)
    
    # Initialize background tasks after bot starts
    app.post_init = lambda app: post_init(app)

    # Run bot
    logger.info("Bot is running and polling for messages")
    app.run_polling(poll_interval=3, close_loop=False, drop_pending_updates=True)
