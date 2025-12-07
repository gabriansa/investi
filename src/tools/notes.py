import uuid
import json
import pickle
import numpy as np
from datetime import datetime, timezone
from typing import Literal
from agents import RunContextWrapper, function_tool
from src.agent.context import Context
from src.services.database import get_db_connection
from src.tools.types import TOPICS, TopicLiteral, RoleLiteral
from src.utils import validate_date


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    vec1_arr = np.array(vec1)
    vec2_arr = np.array(vec2)
    return np.dot(vec1_arr, vec2_arr) / (np.linalg.norm(vec1_arr) * np.linalg.norm(vec2_arr))


def create_embedding(client, note_text: str, embedding_model: str) -> list[float]:
    """Generate an embedding for a note using the configured embedding model."""
    response = client.embeddings.create(
        model=embedding_model,
        input=note_text
    )
    return response.data[0].embedding


@function_tool
def create_note(
    ctx: RunContextWrapper[Context],
    note: str,
    topic: TopicLiteral,
    role: RoleLiteral,
    ticker_symbol: str | None,
    related_note_ids: list[str] | None,
    related_task_ids: list[str] | None,
    related_watchlist_ids: list[str] | None,
    ):
    f"""
    Creates a permanent note in the memory system. Returns confirmation when the note is saved.

    Args:
        note (required): The detailed note content to store.
        topic (required): Category for this note. Choose from {len(TOPICS)} categories: {TOPICS}
        role (required): Who created this note - "portfolio_manager", "analyst" or "trader".
        ticker_symbol (optional): Stock/crypto symbol for asset-specific notes (e.g., "AAPL", "BTC-USD"). Omit for portfolio-level notes.
        related_note_ids (optional): List of note IDs to link to this note. Omit to not link to any notes.
        related_task_ids (optional): List of task IDs to link to this note. Omit to not link to any tasks.
        related_watchlist_ids (optional): List of watchlist IDs to link to this note. Omit to not link to any watchlists.
    """

    note_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    
    # Generate embedding for the note
    embedding = create_embedding(ctx.context.client, note, ctx.context.embedding_model)
    embedding_blob = pickle.dumps(embedding)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO notes (
                note_id, telegram_user_id, created_at, ticker_symbol, topic, role, note,
                related_note_ids, related_task_ids, related_watchlist_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                note_id,
                ctx.context.user_id,
                created_at,
                ticker_symbol,
                topic,
                role,
                note,
                json.dumps(related_note_ids) if related_note_ids else None,
                json.dumps(related_task_ids) if related_task_ids else None,
                json.dumps(related_watchlist_ids) if related_watchlist_ids else None,
            )
        )
        
        # Store the embedding
        cursor.execute(
            """INSERT INTO note_embeddings (note_id, embedding)
               VALUES (?, ?)""",
            (note_id, embedding_blob)
        )

    return f"Note with ID {note_id} added successfully"

@function_tool
def search_notes(
    ctx: RunContextWrapper[Context],
    search_query: str | None,
    ticker_symbols: list[str] | None = None,
    topics: list[TopicLiteral] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 10,
    order_by: Literal["relevant", "recent"] = "recent",
    ):
    """
    Searches and retrieves notes from the memory system using semantic search and/or filters.
    At least one parameter must be provided.

    Args:
        search_query (optional): Semantic search query to find relevant notes by meaning. Can be combined with other filters.
        ticker_symbols (optional): List of stock/crypto symbols to filter by (e.g., ["AAPL", "MSFT", "BTC/USD"]).
        topics (optional): List of topic categories to filter by (e.g., ["RISK_FACTORS", "ALLOCATION"]).
        start_date (optional): Filter notes on or after this date in YYYY-MM-DD format.
        end_date (optional): Filter notes on or before this date in YYYY-MM-DD format.
        limit (optional): Maximum number of results to return (default: 10).
        order_by (optional): How to order results - "relevant" (balances relevance + recency) or "recent" (prioritizes date, default).
    """
    # At least one filter must be provided
    if not search_query and not ticker_symbols and not topics and not start_date and not end_date:
        return {"error": "At least one filter (search_query, ticker_symbols, topics, start_date, or end_date) must be provided."}
    
    # Build common filter conditions
    filter_conditions = []
    filter_params = []
    
    if ticker_symbols:
        placeholders = ','.join(['?'] * len(ticker_symbols))
        filter_conditions.append(f"LOWER(ticker_symbol) IN ({placeholders})")
        filter_params.extend([s.lower() for s in ticker_symbols])
    
    if topics:
        placeholders = ','.join(['?'] * len(topics))
        filter_conditions.append(f"UPPER(topic) IN ({placeholders})")
        filter_params.extend([t.upper() for t in topics])
    
    if start_date:
        success, start_dt = validate_date(start_date, output_format="%Y-%m-%d %H:%M:%S %Z")
        if not success:
            return {"error": f"Invalid start_date format. Use YYYY-MM-DD format (e.g., '2024-01-01'). Provided: {start_date}"}
        filter_conditions.append("created_at >= ?")
        filter_params.append(start_dt)
    
    if end_date:
        success, end_dt = validate_date(end_date, output_format="%Y-%m-%d %H:%M:%S %Z")
        if not success:
            return {"error": f"Invalid end_date format. Use YYYY-MM-DD format (e.g., '2024-12-31'). Provided: {end_date}"}
        filter_conditions.append("created_at < ?")
        filter_params.append(end_dt)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # PATH 1: No search query - simple filter-based retrieval ordered by date
        if not search_query:
            query = "SELECT * FROM notes WHERE telegram_user_id = ?"
            params = [ctx.context.user_id] + filter_params
            
            if filter_conditions:
                query += " AND " + " AND ".join(filter_conditions)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            
            if not results:
                return {"error": "No notes found for the given filters"}
            
            return results
        
        # PATH 2: With search query - semantic search with smart ranking
        else:
            # Generate embedding for search query
            query_embedding = create_embedding(ctx.context.client, search_query, ctx.context.embedding_model)
            
            # Build query with filters
            query = """
                SELECT n.*, ne.embedding
                FROM notes n
                JOIN note_embeddings ne ON n.note_id = ne.note_id
                WHERE n.telegram_user_id = ?
            """
            params = [ctx.context.user_id] + filter_params
            
            if filter_conditions:
                # Add 'n.' prefix for joined table
                prefixed_conditions = [cond.replace("ticker_symbol", "n.ticker_symbol")
                                      .replace("topic", "n.topic")
                                      .replace("created_at", "n.created_at") 
                                      for cond in filter_conditions]
                query += " AND " + " AND ".join(prefixed_conditions)
            
            # Limit to 500 for performance
            query += " LIMIT 500"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            if not rows:
                return {"error": "No notes found matching the search query and filters"}
            
            # Calculate similarities and recency scores for all retrieved notes
            now = datetime.now(timezone.utc)
            all_results = []
            
            for row in rows:
                note_dict = dict(row)
                embedding_blob = note_dict.pop('embedding')
                note_embedding = pickle.loads(embedding_blob)
                
                # Calculate similarity score
                similarity = cosine_similarity(query_embedding, note_embedding)
                note_dict['similarity_score'] = float(similarity)
                
                # Calculate recency score (0-1 scale, exponential decay)
                # Notes from today = 1.0, notes from 30 days ago ≈ 0.5, older = lower
                created_at = datetime.strptime(note_dict['created_at'], "%Y-%m-%d %H:%M:%S %Z").replace(tzinfo=timezone.utc)
                days_old = (now - created_at).total_seconds() / 86400
                recency_score = np.exp(-days_old / 30.0)  # 30-day half-life
                
                # Calculate combined scores for both ordering modes
                if order_by == "relevant":
                    # Relevant mode: 70% relevance, 30% recency
                    # Notes need to be both relevant AND recent to rank high
                    note_dict['combined_score'] = (0.7 * similarity) + (0.3 * recency_score)
                else:  # order_by == "recent"
                    # Recent mode: 60% recency, 40% relevance
                    # Prioritizes newer notes while still considering relevance
                    note_dict['combined_score'] = (0.6 * recency_score) + (0.4 * similarity)
                
                all_results.append(note_dict)
            
            # Sort by combined score (balances relevance and recency)
            all_results.sort(key=lambda x: x['combined_score'], reverse=True)
            
            # Apply limit
            all_results = all_results[:limit]

            return all_results

@function_tool
def get_related_notes(
    ctx: RunContextWrapper[Context],
    note_ids: list[str],
    limit: int | None,
    ):
    """
    Retrieves notes related to the given note IDs, recursively following all relationships.
    Returns notes ordered by creation date (newest first).

    Args:
        note_ids (required): List of note IDs to start from.
        limit (optional): Maximum number of results to return. Omit to return all related notes.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        all_note_ids = set()
        
        def collect_related_ids(ids_to_process):
            for note_id in ids_to_process:
                if note_id in all_note_ids:
                    continue
                all_note_ids.add(note_id)
                
                # Get this note's related_note_ids
                cursor.execute(
                    "SELECT related_note_ids FROM notes WHERE telegram_user_id = ? AND note_id = ?",
                    [ctx.context.user_id, note_id]
                )
                row = cursor.fetchone()
                if row and row['related_note_ids']:
                    try:
                        related_ids = json.loads(row['related_note_ids']) if isinstance(row['related_note_ids'], str) else row['related_note_ids']
                        if related_ids:
                            collect_related_ids(related_ids)
                    except (json.JSONDecodeError, TypeError):
                        pass
        
        # Start collection from provided note_ids
        collect_related_ids(note_ids)
        
        if not all_note_ids:
            return {"error": "No related notes found"}
        
        # Get all collected notes ordered by date (newest first)
        placeholders = ','.join(['?'] * len(all_note_ids))
        query = f"SELECT * FROM notes WHERE telegram_user_id = ? AND note_id IN ({placeholders}) ORDER BY created_at DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, [ctx.context.user_id] + list(all_note_ids))
        results = [dict(row) for row in cursor.fetchall()]
        
        if not results:
            return {"error": "No related notes found"}
        
        return results
