import asyncio
import logging
import os

import yaml
from dotenv import load_dotenv

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest

from agents import set_trace_processors
from langsmith.wrappers import OpenAIAgentsTracingProcessor

from src.bot.commands import (
    start_command,
    set_alpaca_command,
    set_openrouter_command,
    set_operating_framework_command,
    empty_command,
    status_command,
    tasks_command,
    alerts_command,
    watchlists_command,
    delete_account_command,
)
from src.bot.handlers import handle_message, error_handler
from src.services.credit_monitor import check_credits
from src.services.database import init_database, close_pool
from src.services.task_engine import check_tasks
from src.utils import setup_logger, send_markdown_message

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
    """Initialize database and background tasks after bot starts."""
    
    # Initialize database in the bot's event loop
    await init_database()
    logger.info("Database initialized")
    
    async def send_message_callback(message: str, user_id: int):
        """Send notification with proper markdown formatting."""
        try:
            await send_markdown_message(application.bot, user_id, message)
        except Exception as e:
            logger.error(f"Error sending notification to user {user_id}: {e}")
    
    # Start task engine
    asyncio.create_task(check_tasks(
        send_message_callback,
        config=config
    ))
    logger.info("Task engine started")
    
    # Start credit monitoring
    asyncio.create_task(check_credits(
        send_message_callback,
        config=config
    ))
    logger.info("Credit monitoring started")


async def post_shutdown(application: Application):
    """Cleanup on shutdown."""
    logger.info("Closing database connection pool...")
    await close_pool()


if __name__ == "__main__":
    logger.info("Starting bot...")
    
    # Configure request with longer timeouts for better reliability
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=10.0,
        read_timeout=10.0,
        write_timeout=10.0,
    )
    
    # Build application
    app = Application.builder().token(token).request(request).build()

    app.add_handler(CommandHandler("start", lambda update, context: start_command(update)))
    app.add_handler(CommandHandler("status", lambda update, context: status_command(update)))
    app.add_handler(CommandHandler("tasks", lambda update, context: tasks_command(update)))
    app.add_handler(CommandHandler("alerts", lambda update, context: alerts_command(update)))
    app.add_handler(CommandHandler("watchlists", lambda update, context: watchlists_command(update)))
    app.add_handler(CommandHandler("set_alpaca", lambda update, context: set_alpaca_command(update, context)))
    app.add_handler(CommandHandler("set_openrouter", lambda update, context: set_openrouter_command(update, context)))
    app.add_handler(CommandHandler("set_operating_framework", lambda update, context: set_operating_framework_command(update, context)))
    app.add_handler(CommandHandler("empty", lambda update, context: empty_command(update, context)))
    app.add_handler(CommandHandler("delete_account", lambda update, context: delete_account_command(update)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: handle_message(update, context, config)))
    app.add_error_handler(error_handler)
    
    # Initialize background tasks after bot starts
    app.post_init = lambda app: post_init(app)
    
    # Cleanup on shutdown
    app.post_shutdown = lambda app: post_shutdown(app)

    # Run bot
    logger.info("Bot is running and polling for messages")
    app.run_polling(poll_interval=2, close_loop=False, drop_pending_updates=True)
