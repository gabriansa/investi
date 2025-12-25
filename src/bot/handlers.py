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
    
    # Check if user is awaiting account deletion confirmation
    if context.user_data.get('awaiting_account_deletion_confirmation'):
        logger.info(f"User {telegram_user_id} responding to account deletion confirmation")
        
        # Check if user typed the exact confirmation phrase
        if text.strip() == "I want to delete my account":
            context.user_data['awaiting_account_deletion_confirmation'] = False
            
            success, message = await user_service.delete_account(telegram_user_id)
            
            if success:
                logger.info(f"User {telegram_user_id} successfully deleted their account")
            
            await send_markdown_message(context.bot, update.effective_chat.id, message)
            return
        else:
            # User didn't type the correct confirmation
            context.user_data['awaiting_account_deletion_confirmation'] = False
            error_message = (
                "The confirmation phrase was not correct.\n\n"
                "If you still want to delete your account, please use /delete_account again."
            )
            await send_markdown_message(context.bot, update.effective_chat.id, error_message)
            return
    
    # Check if user is awaiting operating framework input
    if context.user_data.get('awaiting_operating_framework'):
        logger.info(f"User {telegram_user_id} submitting operating framework")
        
        # Validate format: all non-empty lines must start with "- "
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        if not lines or not all(line.startswith('- ') for line in lines):
            error_message = (
                "Wrong format. Please use this format:\n\n"
                "- principle one\n"
                "- principle two\n"
                "- principle three\n\n"
                "Send /empty to keep it empty or /cancel to cancel."
            )
            await send_markdown_message(context.bot, update.effective_chat.id, error_message)
            return
        
        # Format is valid, save the framework
        context.user_data['awaiting_operating_framework'] = False
        _, message = await user_service.set_operating_framework(telegram_user_id, text.strip())
        logger.info(f"User {telegram_user_id} successfully set operating framework")
        await send_markdown_message(context.bot, update.effective_chat.id, message)
        return
    
    # Check if user is awaiting Alpaca credentials
    if context.user_data.get('awaiting_alpaca_credentials'):
        # Delete the message containing secrets
        try:
            await update.message.delete()
        except Exception:
            pass
        
        logger.info(f"User {telegram_user_id} submitting Alpaca credentials")
        
        # Parse the credentials - expecting "api_key secret_key"
        parts = text.strip().split()
        if len(parts) != 2:
            error_message = (
                "Wrong format. Please send your credentials as:\n\n"
                "`<api_key> <secret_key>`\n\n"
                "Send /cancel to cancel."
            )
            await send_markdown_message(context.bot, update.effective_chat.id, error_message)
            return
        
        api_key, secret_key = parts[0], parts[1]
        
        # Validate credentials
        is_valid, message = await asyncio.to_thread(
            user_service.validate_alpaca_credentials, api_key, secret_key
        )
        
        if not is_valid:
            logger.warning(f"User {telegram_user_id} provided invalid Alpaca credentials")
            error_message = (
                f"{message}\n\n"
                "Please try again or send /cancel to cancel."
            )
            await send_markdown_message(context.bot, update.effective_chat.id, error_message)
            return
        
        # Credentials are valid, save them
        context.user_data['awaiting_alpaca_credentials'] = False
        _, message = await user_service.set_alpaca_credentials(telegram_user_id, api_key, secret_key)
        logger.info(f"User {telegram_user_id} successfully set Alpaca credentials")
        await send_markdown_message(context.bot, update.effective_chat.id, message)
        return
    
    # Check if user is awaiting OpenRouter API key
    if context.user_data.get('awaiting_openrouter_key'):
        # Delete the message containing secrets
        try:
            await update.message.delete()
        except Exception:
            pass
        
        logger.info(f"User {telegram_user_id} submitting OpenRouter API key")
        
        api_key = text.strip()
        
        # Validate API key
        is_valid, message = await asyncio.to_thread(
            user_service.validate_openrouter_credentials, api_key
        )
        
        if not is_valid:
            logger.warning(f"User {telegram_user_id} provided invalid OpenRouter API key")
            error_message = (
                f"{message}\n\n"
                "Please try again or send /cancel to cancel."
            )
            await send_markdown_message(context.bot, update.effective_chat.id, error_message)
            return
        
        # API key is valid, save it
        context.user_data['awaiting_openrouter_key'] = False
        _, message = await user_service.set_openrouter_credentials(telegram_user_id, api_key)
        logger.info(f"User {telegram_user_id} successfully set OpenRouter API key")
        await send_markdown_message(context.bot, update.effective_chat.id, message)
        return
    
    logger.info(f"User request from {username} (ID: {telegram_user_id}): {text[:100]}{'...' if len(text) > 100 else ''}")
    
    user, message = await user_service.get_user(telegram_user_id)
    if user is None:
        logger.warning(f"User {telegram_user_id} not found in database")
        await send_markdown_message(context.bot, update.effective_chat.id, message)
        return
    
    has_enough_credits, message = await asyncio.to_thread(
        user_service.has_enough_credits, user['openrouter_api_key'], min_credits_to_run
    )
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
    message = f"<user_message>{text}</user_message>"
    result = await agent.run(message)
    
    logger.info(f"Completed request for user {telegram_user_id}")

    # Send with proper markdown formatting and chunking
    await send_markdown_message(context.bot, update.effective_chat.id, result)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error: {context.error}")
    logger.error(traceback.format_exc())
