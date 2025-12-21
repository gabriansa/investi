import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from src.services import UserService
from src.utils import send_markdown_message

logger = logging.getLogger(__name__)


async def start_command(update: Update):
    """Handle /start command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id
    telegram_username = update.effective_user.username
    username = telegram_username or update.effective_user.first_name or "Unknown"
    
    logger.info(f"User {username} (ID: {telegram_user_id}) executed /start command")

    _, message = await user_service.register_user(telegram_user_id, telegram_username)

    await send_markdown_message(update.get_bot(), update.effective_chat.id, message)
    
async def set_alpaca_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_alpaca command."""
    telegram_user_id = update.effective_user.id
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    
    logger.info(f"User {telegram_user_id} executed /set_alpaca command")
    
    user_service = UserService()
    exists, message = await user_service.user_exists(telegram_user_id)
    
    if not exists:
        await send_markdown_message(bot, chat_id, message)
        return
    
    # Set state to indicate we're waiting for alpaca credentials
    context.user_data['awaiting_alpaca_credentials'] = True
    
    instructions = (
        "OK. Send me your Alpaca credentials in this format:\n\n"
        "`<api_key> <secret_key>`\n\n"
        "Send /cancel to cancel."
    )
    await send_markdown_message(bot, chat_id, instructions)

async def set_openrouter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_openrouter command."""
    telegram_user_id = update.effective_user.id
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    
    logger.info(f"User {telegram_user_id} executed /set_openrouter command")
    
    user_service = UserService()
    exists, message = await user_service.user_exists(telegram_user_id)
    
    if not exists:
        await send_markdown_message(bot, chat_id, message)
        return
    
    # Set state to indicate we're waiting for openrouter api key
    context.user_data['awaiting_openrouter_key'] = True
    
    instructions = (
        "OK. Send me your OpenRouter API key.\n\n"
        "Send /cancel to cancel."
    )
    await send_markdown_message(bot, chat_id, instructions)

async def set_operating_framework_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_operating_framework command."""
    telegram_user_id = update.effective_user.id
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    
    logger.info(f"User {telegram_user_id} executed /set_operating_framework command")
    
    user_service = UserService()
    exists, message = await user_service.user_exists(telegram_user_id)
    
    if not exists:
        await send_markdown_message(bot, chat_id, message)
        return
    
    # Set state to indicate we're waiting for framework input
    context.user_data['awaiting_operating_framework'] = True
    
    instructions = (
        "OK. Send me the new operating framework. Please use this format:\n\n"
        "- principle one\n"
        "- principle two\n"
        "- principle three\n\n"
        "Send /empty to keep it empty or /cancel to cancel."
    )
    await send_markdown_message(bot, chat_id, instructions)

async def empty_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /empty command to clear operating framework."""
    telegram_user_id = update.effective_user.id
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    
    # Check if user is in the awaiting framework state
    if not context.user_data.get('awaiting_operating_framework'):
        await send_markdown_message(bot, chat_id, "Unrecognized command.")
        return
    
    logger.info(f"User {telegram_user_id} clearing operating framework")
    
    user_service = UserService()
    context.user_data['awaiting_operating_framework'] = False
    
    _, message = await user_service.set_operating_framework(telegram_user_id, "")
    logger.info(f"User {telegram_user_id} cleared operating framework")
    await send_markdown_message(bot, chat_id, "Operating framework updated successfully")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command to cancel credential or framework updates."""
    telegram_user_id = update.effective_user.id
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    
    # Check which state the user is in
    if context.user_data.get('awaiting_operating_framework'):
        logger.info(f"User {telegram_user_id} cancelled operating framework update")
        context.user_data['awaiting_operating_framework'] = False
        await send_markdown_message(bot, chat_id, "Operating framework update cancelled. Your existing framework remains unchanged.")
    elif context.user_data.get('awaiting_alpaca_credentials'):
        logger.info(f"User {telegram_user_id} cancelled Alpaca credentials update")
        context.user_data['awaiting_alpaca_credentials'] = False
        await send_markdown_message(bot, chat_id, "Alpaca credentials update cancelled.")
    elif context.user_data.get('awaiting_openrouter_key'):
        logger.info(f"User {telegram_user_id} cancelled OpenRouter key update")
        context.user_data['awaiting_openrouter_key'] = False
        await send_markdown_message(bot, chat_id, "OpenRouter key update cancelled.")
    else:
        await send_markdown_message(bot, chat_id, "Unrecognized command.")

async def status_command(update: Update):
    """Handle /status command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    
    logger.info(f"User {telegram_user_id} executed /status command")

    response = await user_service.get_status(telegram_user_id)
    await send_markdown_message(bot, chat_id, response)

async def tasks_command(update: Update):
    """Handle /tasks command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    
    logger.info(f"User {telegram_user_id} executed /tasks command")

    response = await user_service.get_tasks(telegram_user_id)
    await send_markdown_message(bot, chat_id, response)

async def watchlists_command(update: Update):
    """Handle /watchlists command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    
    logger.info(f"User {telegram_user_id} executed /watchlists command")

    response = await user_service.get_watchlists(telegram_user_id)
    await send_markdown_message(bot, chat_id, response)

async def delete_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /delete_account command."""
    user_service = UserService()
    telegram_user_id = update.effective_user.id
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    
    logger.info(f"User {telegram_user_id} executed /delete_account command")
    
    exists, message = await user_service.user_exists(telegram_user_id)
    
    if not exists:
        await send_markdown_message(bot, chat_id, message)
        return
    
    # Set state to indicate we're waiting for deletion confirmation
    context.user_data['awaiting_account_deletion_confirmation'] = True
    
    confirmation_message = (
        "This action is *permanent* and will delete:\n"
        "• Your account and all settings\n"
        "• All saved notes and data\n"
        "• All tasks and alerts\n"
        "• All watchlists\n\n"
        "To confirm, please type exactly:\n"
        "`I want to delete my account`\n\n"
        "To cancel, send any other message or use /delete_account again."
    )
    await send_markdown_message(bot, chat_id, confirmation_message)
