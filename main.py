import asyncio
import logging
import os
import signal

import yaml
from dotenv import load_dotenv

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest

from agents import set_trace_processors
from langsmith.integrations.openai_agents_sdk import OpenAIAgentsTracingProcessor


from src.bot.commands import (
    start_command,
    set_alpaca_command,
    set_openrouter_command,
    set_operating_framework_command,
    empty_command,
    cancel_command,
    status_command,
    tasks_command,
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
    
    # Broadcast startup message to all users
    try:
        from src.services.database import get_async_db_connection
        async with get_async_db_connection() as conn:
            user_ids = await conn.fetch("SELECT telegram_user_id FROM users")
        
        if user_ids:
            logger.info(f"Broadcasting startup message to {len(user_ids)} users")
            
            async def send_startup(user_id):
                try:
                    await send_markdown_message(
                        application.bot, 
                        user_id, 
                        "**Investi is back online**"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id}: {e}")
            
            # Send all messages in parallel
            await asyncio.gather(*[send_startup(row['telegram_user_id']) for row in user_ids])
    except Exception as e:
        logger.error(f"Error broadcasting startup: {e}")


async def broadcast_shutdown(application: Application):
    """Broadcast shutdown message to all users."""
    try:
        from src.services.database import get_async_db_connection
        async with get_async_db_connection() as conn:
            user_ids = await conn.fetch("SELECT telegram_user_id FROM users")
        
        if user_ids:
            logger.info(f"Broadcasting shutdown message to {len(user_ids)} users")
            
            async def send_shutdown(user_id):
                try:
                    await send_markdown_message(
                        application.bot, 
                        user_id, 
                        "**Investi is shutting down for maintenance purposes**\nTry again in a moment. You will be notified when it's back online."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id}: {e}")
            
            # Send all messages in parallel
            await asyncio.gather(*[send_shutdown(row['telegram_user_id']) for row in user_ids])
    except Exception as e:
        logger.error(f"Error broadcasting shutdown: {e}")


async def post_shutdown(application: Application):
    """Cleanup on shutdown."""
    logger.info("Closing database connection pool...")
    await close_pool()


async def run_bot():
    """Run the bot with graceful shutdown."""
    # Configure request with longer timeouts for better reliability
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=10.0,
        read_timeout=30.0,  # Increased for long polling
        write_timeout=10.0,
        pool_timeout=30.0,  # Added pool timeout
    )
    
    # Build application
    app = Application.builder().token(token).request(request).build()

    app.add_handler(CommandHandler("start", lambda update, context: start_command(update)))
    app.add_handler(CommandHandler("status", lambda update, context: status_command(update)))
    app.add_handler(CommandHandler("tasks", lambda update, context: tasks_command(update)))
    app.add_handler(CommandHandler("watchlists", lambda update, context: watchlists_command(update)))
    app.add_handler(CommandHandler("set_alpaca", lambda update, context: set_alpaca_command(update, context)))
    app.add_handler(CommandHandler("set_openrouter", lambda update, context: set_openrouter_command(update, context)))
    app.add_handler(CommandHandler("set_operating_framework", lambda update, context: set_operating_framework_command(update, context)))
    app.add_handler(CommandHandler("empty", lambda update, context: empty_command(update, context)))
    app.add_handler(CommandHandler("cancel", lambda update, context: cancel_command(update, context)))
    app.add_handler(CommandHandler("delete_account", lambda update, context: delete_account_command(update, context)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: handle_message(update, context, config)))
    app.add_error_handler(error_handler)
    
    # Initialize and run
    await app.initialize()
    await post_init(app)
    await app.start()
    await app.updater.start_polling(poll_interval=2, drop_pending_updates=True)
    
    logger.info("Bot is running and polling for messages")
    
    # Wait for stop signal
    stop_event = asyncio.Event()
    
    def signal_handler(signum, frame):
        logger.info(f"Received shutdown signal ({signum})")
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await stop_event.wait()
    
    # Broadcast shutdown before stopping
    await broadcast_shutdown(app)
    
    # Stop bot
    await app.updater.stop()
    await app.stop()
    await post_shutdown(app)
    await app.shutdown()
    logger.info("Bot stopped")


if __name__ == "__main__":
    logger.info("Starting bot...")
    asyncio.run(run_bot())
