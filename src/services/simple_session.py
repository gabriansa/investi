"""
Simple session implementation that only stores essential conversation messages.
Excludes tool calls and tool responses to minimize token usage.
"""

from agents.memory.session import SessionABC
from agents.items import TResponseInputItem
from typing import List
from datetime import datetime, timezone
from src.services.database import get_pool
import logging

logger = logging.getLogger(__name__)


class SimpleSession(SessionABC):
    """
    Lightweight session implementation that stores only essential messages:
    - System messages
    - User messages
    - Assistant messages (final responses)
    
    Excludes tool calls and tool responses to reduce token usage by ~70-80%.
    """
    
    def __init__(self, session_id: str, ttl: int | None = None):
        """
        Initialize a simple session.
        
        Args:
            session_id: Unique identifier for this session
            ttl: Optional time-to-live in seconds (currently not enforced)
        """
        self.session_id = session_id
        self.ttl = ttl
    
    def _filter_essential_items(self, items: List[TResponseInputItem]) -> List[TResponseInputItem]:
        """
        Filter items to only keep essential conversation messages.
        
        Keeps: system, user, assistant
        Excludes: tool calls, tool responses, and assistant messages with tool_calls
        """
        essential_items = []
        for item in items:
            # Keep system and user messages always
            if item.get("role") in ["system", "user"]:
                essential_items.append(item)
            # Keep assistant messages only if they don't have tool_calls
            elif item.get("role") == "assistant":
                # Only keep assistant messages without tool calls (final responses)
                if "tool_calls" not in item or item["tool_calls"] is None:
                    essential_items.append(item)
            # Skip tool role entirely
        return essential_items
    
    async def get_items(self, limit: int | None = None) -> List[TResponseInputItem]:
        """
        Retrieve conversation history for this session.
        
        Args:
            limit: Optional maximum number of items to retrieve (most recent)
        
        Returns:
            List of conversation items in chronological order
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            if limit is None:
                rows = await conn.fetch("""
                    SELECT role, content
                    FROM agent_sessions
                    WHERE session_id = $1
                    ORDER BY item_index ASC
                """, self.session_id)
            else:
                # Get the most recent N items
                rows = await conn.fetch("""
                    SELECT role, content
                    FROM agent_sessions
                    WHERE session_id = $1
                    ORDER BY item_index DESC
                    LIMIT $2
                """, self.session_id, limit)
                # Reverse to get chronological order
                rows = list(reversed(rows))
            
            items = []
            for row in rows:
                items.append({
                    "role": row["role"],
                    "content": row["content"]
                })
            
            return items
    
    async def add_items(self, items: List[TResponseInputItem]) -> None:
        """
        Store new items for this session.
        Only essential messages (system, user, assistant without tool_calls) are stored.
        
        Args:
            items: List of conversation items to add
        """
        # Filter to only essential items
        essential_items = self._filter_essential_items(items)
        
        if not essential_items:
            return
        
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Get the current max index for this session
            max_index_row = await conn.fetchrow("""
                SELECT COALESCE(MAX(item_index), -1) as max_idx
                FROM agent_sessions
                WHERE session_id = $1
            """, self.session_id)
            
            next_index = max_index_row["max_idx"] + 1
            
            # Insert each essential item
            for idx, item in enumerate(essential_items):
                await conn.execute("""
                    INSERT INTO agent_sessions (session_id, item_index, role, content, created_at)
                    VALUES ($1, $2, $3, $4, $5)
                """, 
                    self.session_id,
                    next_index + idx,
                    item["role"],
                    item.get("content", ""),
                    datetime.now(timezone.utc)
                )
            
            logger.debug(f"Stored {len(essential_items)} essential items for session {self.session_id}")
    
    async def pop_item(self) -> TResponseInputItem | None:
        """
        Remove and return the most recent item from this session.
        
        Returns:
            The most recent item, or None if session is empty
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Get the most recent item
            row = await conn.fetchrow("""
                SELECT item_index, role, content
                FROM agent_sessions
                WHERE session_id = $1
                ORDER BY item_index DESC
                LIMIT 1
            """, self.session_id)
            
            if row is None:
                return None
            
            # Delete it
            await conn.execute("""
                DELETE FROM agent_sessions
                WHERE session_id = $1 AND item_index = $2
            """, self.session_id, row["item_index"])
            
            return {
                "role": row["role"],
                "content": row["content"]
            }
    
    async def clear_session(self) -> None:
        """
        Clear all items for this session.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM agent_sessions
                WHERE session_id = $1
            """, self.session_id)
            
            logger.debug(f"Cleared session {self.session_id}")

