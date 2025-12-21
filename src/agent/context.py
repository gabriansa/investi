from dataclasses import dataclass
from openai import AsyncOpenAI
from src.api.alpaca import AlpacaAPI
from src.api.yahoo_finance import YFinanceAPI


@dataclass
class Context:
    client: AsyncOpenAI
    alpaca_api: AlpacaAPI
    yfinance_api: YFinanceAPI
    todos: list
    user_id: int
    embedding_model: str
    web_search_model: str
    screener_finder_model: str
