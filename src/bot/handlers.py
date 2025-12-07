import traceback
from telegram import Update
from telegram.ext import ContextTypes
from src.agent import InvestiAgent
from src.services.user_service import UserService


async def handle_message(update: Update, config: dict):
    """Handle incoming user messages."""
    import asyncio
    asyncio.create_task(_process_message(update, config))

async def _process_message(update: Update, config: dict):
    """Process message in background."""
    min_credits_to_run = config['credits']['min_credits_to_run']

    text = update.message.text
    
    user_service = UserService()
    telegram_user_id = update.effective_user.id
    
    user, message = user_service.get_user(telegram_user_id)
    if user is None:
        await update.message.reply_text(message, parse_mode='Markdown')
        return
    
    has_enough_credits, message = user_service.has_enough_credits(user['openrouter_api_key'], min_credits_to_run)
    if not has_enough_credits:
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

    await update.message.reply_text(result, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    print(f"Update {update} caused error {context.error}")
    traceback.print_exc()

