from typing import Any
from openai import AsyncOpenAI
import tiktoken


def _count_message_tokens(message: dict[str, Any]) -> int:
    """Count tokens in a message using tiktoken."""
    encoding = tiktoken.get_encoding("cl100k_base")
    
    content = message.get("content", "")
    if isinstance(content, str):
        return len(encoding.encode(content))
    elif isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, dict) and "text" in item:
                total += len(encoding.encode(item["text"]))
        return total
    return 0


def _add_cache_control(messages: list[dict[str, Any]], max_cache_blocks: int = 4, min_tokens: int = 1024) -> list[dict[str, Any]]:
    """Add cache_control to the largest messages by token count.
    
    Strategy:
    1. Count tokens in each message
    2. Only consider messages with >= min_tokens (default 1024)
    3. Select top 4 largest messages by token count
    """
    if not messages:
        return messages
    
    # Calculate token counts and create candidates
    candidates = []
    for i, msg in enumerate(messages):
        token_count = _count_message_tokens(msg)
        if token_count >= min_tokens:
            candidates.append({
                "index": i,
                "token_count": token_count
            })
    
    # Sort by token count and select top N
    candidates.sort(key=lambda x: x["token_count"], reverse=True)
    indices_to_cache = {c["index"] for c in candidates[:max_cache_blocks]}
    
    # Apply cache_control to selected messages
    result = []
    for i, msg in enumerate(messages):
        new_msg = msg.copy()
        
        if i in indices_to_cache:
            content = new_msg.get("content")
            
            if isinstance(content, str):
                # Convert string content to list with cache_control
                new_msg["content"] = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
            elif isinstance(content, list) and len(content) > 0:
                # Only add cache_control to the LAST content block in the list
                new_content = [item.copy() if isinstance(item, dict) else item for item in content]
                last_item = new_content[-1]
                
                if isinstance(last_item, dict) and last_item.get("type") == "text" and "cache_control" not in last_item:
                    last_item["cache_control"] = {"type": "ephemeral"}
                
                new_msg["content"] = new_content
        
        result.append(new_msg)
    
    return result


def enable_caching(client: AsyncOpenAI) -> AsyncOpenAI:
    """Enable OpenRouter caching by patching the client.
    
    Usage:
        client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key="...")
        client = enable_caching(client)
    """
    original_create = client.chat.completions.create
    
    async def cached_create(*args, **kwargs):
        if "messages" in kwargs:
            kwargs["messages"] = _add_cache_control(kwargs["messages"])
        return await original_create(*args, **kwargs)
    
    client.chat.completions.create = cached_create
    return client
