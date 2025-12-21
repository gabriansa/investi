from typing import Literal
from agents import RunContextWrapper, function_tool
from src.agent.context import Context
from pydantic import BaseModel
import json


class Todo(BaseModel):
    """Todo to track"""
    content: str
    status: Literal["pending", "in_progress", "completed"]


@function_tool
def write_todos(
    ctx: RunContextWrapper[Context],
    todos: list[Todo]
    ):
    """
    Creates or updates a todo list for tracking multi-step tasks. Each call replaces the entire todo list.
    Returns confirmation of the updated list.

    Args:
        todos (required): Complete list of Todo items. Each Todo has content (task description) and status ("pending", "in_progress", or "completed").
    """
    ctx.context.todos = todos

    # return f"Updated todo list to {todos}"
    return "Todo list updated"
