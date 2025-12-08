import asyncio
import logging
import telegramify_markdown

logger = logging.getLogger(__name__)


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


async def send_bot_markdown_message(bot, chat_id: int, message: str, max_length: int = 4096):
    """Send markdown message using bot instance (for background tasks)."""
    try:
        # Convert markdown to Telegram-friendly format
        converted = telegramify_markdown.markdownify(message)
        chunks = chunk_text(converted, max_length)
        
        # Send all chunks with MarkdownV2
        for i, chunk in enumerate(chunks, 1):
            try:
                await bot.send_message(chat_id=chat_id, text=chunk, parse_mode='MarkdownV2')
                if i < len(chunks):
                    await asyncio.sleep(0.3)
            except Exception as e:
                # If MarkdownV2 fails, log error and send as plain text
                logger.warning(f"Failed to send chunk {i}/{len(chunks)} with MarkdownV2: {e}")
                await bot.send_message(chat_id=chat_id, text=chunk)
                if i < len(chunks):
                    await asyncio.sleep(0.3)
    except Exception as e:
        # If telegramify fails, fall back to chunking and sending original message as plain text
        logger.error(f"Failed to convert markdown: {e}")
        chunks = chunk_text(message, max_length)
        for i, chunk in enumerate(chunks, 1):
            await bot.send_message(chat_id=chat_id, text=chunk)
            if i < len(chunks):
                await asyncio.sleep(0.3)
