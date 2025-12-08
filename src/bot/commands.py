import logging
from telegram import Update
from telegram.ext import ContextTypes
from src.services import UserService

logger = logging.getLogger(__name__)


async def start_command(update: Update):
    """Handle /start command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "Unknown"
    
    logger.info(f"User {username} (ID: {telegram_user_id}) executed /start command")

    _, message = user_service.register_user(telegram_user_id)

    await update.message.reply_text(message, parse_mode='Markdown')
    
async def set_alpaca_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_alpaca command."""
    telegram_user_id = update.effective_user.id
    
    if not context.args or len(context.args) != 2:
        await update.message.reply_text("Usage: `/set_alpaca <api_key> <secret_key>`", parse_mode='Markdown')
        return

    # Delete the message containing secrets
    try:
        await update.message.delete()
    except Exception:
        pass  # Silently fail if bot lacks delete permission

    logger.info(f"User {telegram_user_id} executed /set_alpaca command")
    
    user_service = UserService()

    exists, message = user_service.user_exists(telegram_user_id)

    if not exists:
        await update.message.reply_text(message, parse_mode='Markdown')
        return

    is_valid, message = user_service.validate_alpaca_credentials(context.args[0], context.args[1])
    
    if not is_valid:
        logger.warning(f"User {telegram_user_id} provided invalid Alpaca credentials")
        await update.message.reply_text(message, parse_mode='Markdown')
        return

    _, message = user_service.set_alpaca_credentials(telegram_user_id, context.args[0], context.args[1])
    logger.info(f"User {telegram_user_id} successfully set Alpaca credentials")
    await update.message.reply_text(message, parse_mode='Markdown')

async def set_openrouter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_openrouter command."""
    telegram_user_id = update.effective_user.id
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: `/set_openrouter <api_key>`", parse_mode='Markdown')
        return
    
    # Delete the message containing secrets
    try:
        await update.message.delete()
    except Exception:
        pass  # Silently fail if bot lacks delete permission
    
    logger.info(f"User {telegram_user_id} executed /set_openrouter command")
    
    user_service = UserService()

    exists, message = user_service.user_exists(telegram_user_id)

    if not exists:
        await update.message.reply_text(message, parse_mode='Markdown')
        return

    is_valid, message = user_service.validate_openrouter_credentials(context.args[0])
    
    if not is_valid:
        logger.warning(f"User {telegram_user_id} provided invalid OpenRouter credentials")
        await update.message.reply_text(message, parse_mode='Markdown')
        return

    _, message = user_service.set_openrouter_credentials(telegram_user_id, context.args[0])
    logger.info(f"User {telegram_user_id} successfully set OpenRouter credentials")
    await update.message.reply_text(message, parse_mode='Markdown')

async def status_command(update: Update):
    """Handle /status command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id
    
    logger.info(f"User {telegram_user_id} executed /status command")

    response = user_service.get_status(telegram_user_id)
    await update.message.reply_text(response, parse_mode='Markdown')

async def delete_account_command(update: Update):
    """Handle /delete_account command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id
    
    logger.info(f"User {telegram_user_id} executed /delete_account command")

    success, message = user_service.delete_account(telegram_user_id)
    
    if success:
        logger.info(f"User {telegram_user_id} successfully deleted their account")
    
    await update.message.reply_text(message, parse_mode='Markdown')
