from src.agent.context import Context
from agents import Agent, Runner, OpenAIChatCompletionsModel, InputGuardrailTripwireTriggered, ModelSettings
from agents.extensions.memory import SQLAlchemySession, EncryptedSession
from openai import AsyncOpenAI
from langsmith import traceable
from src.agent.prompt_builder import get_analyst_prompt, get_portfolio_manager_prompt, get_trader_prompt, get_guardrail_prompt, get_technical_analyst_prompt
from src.agent.caching import enable_caching
from src.agent.guardrails import create_portfolio_guardrail

import os
from dotenv import load_dotenv

from src.api.yahoo_finance import YFinanceAPI
from src.api.alpaca import AlpacaAPI

from src.tools.assets import fetch_historical_price_data, get_current_market_quote, find_screeners, execute_screener, search_for_symbols, get_company_profile, calculate_technical_indicator
from src.tools.notes import create_note, search_notes, get_notes_by_id
from src.tools.orders import create_order, get_orders, cancel_orders
from src.tools.positions import get_positions, close_position
from src.tools.charts import get_candlestick_chart
from src.tools.tasks import set_one_time_task, set_recurring_task, set_conditional_task, get_tasks, remove_task
from src.tools.searches import search_web, search_sec_filings
from src.tools.watchlists import get_watchlist, create_watchlist, remove_watchlist, modify_watchlist_symbols
from src.tools.write_todos import write_todos
from src.tools.sleep import sleep

load_dotenv()


class InvestiAgent:
    def __init__(
        self, 
        config: dict,
        user_id: int,
        openrouter_api_key: str,
        alpaca_api_key: str,
        alpaca_secret_key: str,
        ):
        
        # Extract config values
        agents_config = config['agents']
        self.portfolio_manager_model = agents_config['portfolio_manager']['model_name']
        self.trader_model = agents_config['trader']['model_name']
        self.analyst_model = agents_config['analyst']['model_name']
        self.technical_analyst_model = agents_config['technical_analyst']['model_name']
        self.guardrail_model = agents_config['guardrail']['model_name']
        self.embedding_model = config['embeddings']['model_name']
        self.web_search_model = config['tools']['web_search_model']
        self.screener_finder_model = config['tools']['screener_finder_model']
        self.portfolio_manager_max_turns = agents_config['portfolio_manager']['max_turns']
        self.trader_max_turns = agents_config['trader']['max_turns']
        self.analyst_max_turns = agents_config['analyst']['max_turns']
        self.technical_analyst_max_turns = agents_config['technical_analyst']['max_turns']
        self.session_ttl = config['session']['ttl_seconds']
        
        # User credentials
        self.openrouter_api_key = openrouter_api_key
        self.alpaca_api_key = alpaca_api_key
        self.alpaca_secret_key = alpaca_secret_key
        self.user_id = user_id
        
        self.client = AsyncOpenAI(base_url=os.getenv("OPENROUTER_BASE_URL"), api_key=self.openrouter_api_key)
        self.cached_client = enable_caching(self.client)
        
        # Model settings with reasoning config
        self.model_settings = ModelSettings(extra_body={"reasoning": {"max_tokens": 2000}})

        # Context
        self.context = Context(
            client=self.client,
            todos=[],
            yfinance_api=YFinanceAPI(),
            alpaca_api=AlpacaAPI(api_key=self.alpaca_api_key,secret_key=self.alpaca_secret_key),
            user_id=self.user_id,
            embedding_model=self.embedding_model,
            web_search_model=self.web_search_model,
            screener_finder_model=self.screener_finder_model
        )

    async def _build_agents(self):
        # Create guardrail function
        self.portfolio_guardrail = create_portfolio_guardrail(
            instructions=get_guardrail_prompt(),
            model=self.guardrail_model,
            openai_client=self.cached_client
        )

        # Technical Analyst Sub-Agent
        self.technical_analyst = Agent[Context](
            name="technical_analyst",
            instructions=get_technical_analyst_prompt(),
            tools=[
                fetch_historical_price_data, get_current_market_quote, calculate_technical_indicator,
                get_candlestick_chart,
            ],
            model=OpenAIChatCompletionsModel(model=self.technical_analyst_model, openai_client=self.cached_client),
            model_settings=self.model_settings
        )
        
        # Analyst Agent
        self.analyst = Agent[Context](
            name="analyst",
            instructions=await get_analyst_prompt(self.user_id),
            tools=[
                get_current_market_quote, find_screeners, execute_screener, search_for_symbols, get_company_profile,
                create_note, search_notes, get_notes_by_id,
                set_one_time_task, set_recurring_task, set_conditional_task, get_tasks, remove_task,
                search_web, search_sec_filings,
                get_watchlist, create_watchlist, remove_watchlist, modify_watchlist_symbols,
                write_todos,
                self.technical_analyst.as_tool(
                    tool_name="technical_analysis",
                    tool_description="Analyzes price action, technical indicators, chart patterns, and provides probabilistic timing signals with key support/resistance levels.",
                    max_turns=self.technical_analyst_max_turns
                ),
                ],
            model=OpenAIChatCompletionsModel(model=self.analyst_model, openai_client=self.cached_client),
            model_settings=self.model_settings
        )

        # Trader Agent
        self.trader = Agent[Context](
            name="trader",
            instructions=await get_trader_prompt(self.user_id),
            tools=[
                create_note, search_notes, get_notes_by_id,
                create_order, get_orders, cancel_orders,
                get_positions, close_position,
                get_current_market_quote,
                set_one_time_task, set_recurring_task, set_conditional_task, get_tasks, remove_task,
                write_todos,
                sleep,
            ],
            model=OpenAIChatCompletionsModel(model=self.trader_model, openai_client=self.cached_client),
            model_settings=self.model_settings
        )

        # Portfolio Manager Agent
        self.portfolio_manager = Agent[Context](
            name="portfolio_manager",
            instructions=await get_portfolio_manager_prompt(self.user_id),
            tools=[
                find_screeners, execute_screener,
                get_current_market_quote,
                create_note, search_notes, get_notes_by_id,
                get_orders,
                get_positions,
                set_one_time_task, set_recurring_task, set_conditional_task, get_tasks, remove_task,
                search_web,
                get_watchlist, create_watchlist, remove_watchlist, modify_watchlist_symbols,
                write_todos,
                self.analyst.as_tool(
                    tool_name="analyst",
                    tool_description="Conducts deep fundamental research, business analysis, competitive positioning, valuation modeling, and produces evidence-backed investment recommendations.",
                    max_turns=self.analyst_max_turns
                ),
                self.trader.as_tool(
                    tool_name="trader",
                    tool_description="Executes buy/sell orders, manages positions and order lifecycle, monitors fills and execution quality for stocks and crypto.",
                    max_turns=self.trader_max_turns
                ),
            ],
            model=OpenAIChatCompletionsModel(model=self.portfolio_manager_model, openai_client=self.cached_client),
            model_settings=self.model_settings,
            input_guardrails=[self.portfolio_guardrail]
        )

    @traceable(name="agent_run", tags=["agent_execution"])
    async def run(self, input: str, use_session: bool = True) -> str:
        # Build agents with fresh data (account, positions, orders, etc.)
        await self._build_agents()
        
        # Use session for user messages, skip for task-triggered runs
        session = None
        if use_session:
            # Convert DATABASE_URL to use asyncpg driver for SQLAlchemy
            db_url = os.getenv("DATABASE_URL")
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
            
            underlying_session = SQLAlchemySession.from_url(
                session_id=f"user_{self.user_id}",
                url=db_url,
                create_tables=True
            )
            session = EncryptedSession(
                session_id=f"user_{self.user_id}",
                underlying_session=underlying_session,
                encryption_key=os.getenv("SESSION_ENCRYPTION_KEY", "default-key-change-in-prod"),
                ttl=self.session_ttl
            )
        
        try:
            result = await Runner.run(
                starting_agent=self.portfolio_manager,
                input=input,
                context=self.context,
                max_turns=self.portfolio_manager_max_turns,
                session=session
            )
            return result.final_output
        except InputGuardrailTripwireTriggered:
            return "Sorry, I can't help with that. Please ask about investing, trading, or portfolio management."
