import traceback
import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
import telegramify_markdown
from src.agent import InvestiAgent
from src.services.user_service import UserService

logger = logging.getLogger(__name__)


async def send_markdown_message(update: Update, message: str, max_length: int = 4096):
    """Send markdown message with proper formatting and chunking for long messages."""
    
    def chunk_text(text: str) -> list:
        """Split text into chunks at natural boundaries."""
        chunks = []
        while len(text) > max_length:
            # Try paragraph break, then line break, then space
            split_pos = text[:max_length].rfind('\n\n')
            if split_pos <= 0:
                split_pos = text[:max_length].rfind('\n')
            if split_pos <= 0:
                split_pos = text[:max_length].rfind(' ')
            split_pos = split_pos if split_pos > 0 else max_length
            chunks.append(text[:split_pos])
            text = text[split_pos:].lstrip()
        if text:
            chunks.append(text)
        return chunks
    
    try:
        # Convert markdown to Telegram-friendly format
        converted = telegramify_markdown.markdownify(message)
        chunks = chunk_text(converted)
        
        # Send all chunks with MarkdownV2
        for i, chunk in enumerate(chunks, 1):
            try:
                await update.message.reply_text(chunk, parse_mode='MarkdownV2')
                if i < len(chunks):
                    await asyncio.sleep(0.3)
            except Exception as e:
                # If MarkdownV2 fails, log error and send as plain text
                logger.warning(f"Failed to send chunk {i}/{len(chunks)} with MarkdownV2: {e}")
                await update.message.reply_text(chunk)
                if i < len(chunks):
                    await asyncio.sleep(0.3)
    except Exception as e:
        # If telegramify fails, fall back to chunking and sending original message as plain text
        logger.error(f"Failed to convert markdown: {e}")
        chunks = chunk_text(message)
        for i, chunk in enumerate(chunks, 1):
            await update.message.reply_text(chunk)
            if i < len(chunks):
                await asyncio.sleep(0.3)


async def handle_message(update: Update, config: dict):
    """Handle incoming user messages."""
    asyncio.create_task(_process_message(update, config))

async def _process_message(update: Update, config: dict):
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
        await update.message.reply_text(message, parse_mode='Markdown')
        return
    
    has_enough_credits, message = user_service.has_enough_credits(user['openrouter_api_key'], min_credits_to_run)
    if not has_enough_credits:
        logger.warning(f"User {telegram_user_id} has insufficient credits")
        await update.message.reply_text(
            message,
            parse_mode='Markdown'
        )
        return
    
    await update.message.reply_text("_Working on it..._", parse_mode='Markdown')

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
    await send_markdown_message(update, result)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error: {context.error}")
    logger.error(traceback.format_exc())

