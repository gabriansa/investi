import asyncio
import logging

from telegram.error import TimedOut
import telegramify_markdown

logger = logging.getLogger(__name__)


async def send_message_with_retry(bot, chat_id: int, text: str, parse_mode: str = 'Markdown', max_retries: int = 2):
    """Send message with automatic retry on timeout."""
    for attempt in range(max_retries):
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, disable_web_page_preview=True)
            return
        except TimedOut:
            if attempt < max_retries - 1:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}, retrying...")
                await asyncio.sleep(1)
            else:
                logger.error(f"Failed to send message after {max_retries} timeout attempts")
                raise

def chunk_text(text: str, max_length: int = 4096) -> list:
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


async def send_markdown_message(bot, chat_id: int, message: str, max_length: int = 4096):
    """Send markdown message with chunking, retry logic, and fallbacks."""
    try:
        # Convert markdown to Telegram-friendly format
        converted = telegramify_markdown.markdownify(message)
        chunks = chunk_text(converted, max_length)
        
        # Send all chunks with MarkdownV2
        for i, chunk in enumerate(chunks, 1):
            try:
                await send_message_with_retry(bot, chat_id, chunk, parse_mode='MarkdownV2')
                if i < len(chunks):
                    await asyncio.sleep(0.3)
            except Exception as e:
                # If MarkdownV2 fails, log error and send as plain text
                logger.warning(f"Failed to send chunk {i}/{len(chunks)} with MarkdownV2: {e}")
                await send_message_with_retry(bot, chat_id, chunk, parse_mode=None)
                if i < len(chunks):
                    await asyncio.sleep(0.3)
    except Exception as e:
        # If telegramify fails, fall back to chunking and sending original message as plain text
        logger.error(f"Failed to convert message to markdown: {e}")
        chunks = chunk_text(message, max_length)
        for i, chunk in enumerate(chunks, 1):
            await send_message_with_retry(bot, chat_id, chunk, parse_mode=None)
            if i < len(chunks):
                await asyncio.sleep(0.3)
