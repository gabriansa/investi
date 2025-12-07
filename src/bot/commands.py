from telegram import Update
from telegram.ext import ContextTypes
from src.services import UserService


async def start_command(update: Update):
    """Handle /start command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id

    _, message = user_service.register_user(telegram_user_id)

    await update.message.reply_text(message, parse_mode='Markdown')
    
async def set_alpaca_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_alpaca command."""
    if not context.args or len(context.args) != 2:
        await update.message.reply_text("Usage: `/set_alpaca <api_key> <secret_key>`", parse_mode='Markdown')
        return

    # Delete the message containing secrets
    try:
        await update.message.delete()
    except Exception:
        pass  # Silently fail if bot lacks delete permission

    user_service = UserService()
    telegram_user_id = update.effective_user.id

    exists, message = user_service.user_exists(telegram_user_id)

    if not exists:
        await update.message.reply_text(message, parse_mode='Markdown')
        return

    is_valid, message = user_service.validate_alpaca_credentials(context.args[0], context.args[1])
    
    if not is_valid:
        await update.message.reply_text(message, parse_mode='Markdown')
        return

    _, message = user_service.set_alpaca_credentials(telegram_user_id, context.args[0], context.args[1])
    await update.message.reply_text(message, parse_mode='Markdown')

async def set_openrouter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_openrouter command."""
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: `/set_openrouter <api_key>`", parse_mode='Markdown')
        return
    
    # Delete the message containing secrets
    try:
        await update.message.delete()
    except Exception:
        pass  # Silently fail if bot lacks delete permission
    
    user_service = UserService()
    telegram_user_id = update.effective_user.id

    exists, message = user_service.user_exists(telegram_user_id)

    if not exists:
        await update.message.reply_text(message, parse_mode='Markdown')
        return

    is_valid, message = user_service.validate_openrouter_credentials(context.args[0])
    
    if not is_valid:
        await update.message.reply_text(message, parse_mode='Markdown')
        return

    _, message = user_service.set_openrouter_credentials(telegram_user_id, context.args[0])
    await update.message.reply_text(message, parse_mode='Markdown')

async def status_command(update: Update):
    """Handle /status command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id

    response = user_service.get_status(telegram_user_id)
    await update.message.reply_text(response, parse_mode='Markdown')

async def delete_account_command(update: Update):
    """Handle /delete_account command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id

    success, message = user_service.delete_account(telegram_user_id)
    await update.message.reply_text(message, parse_mode='Markdown')
