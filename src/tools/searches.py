from typing import Literal
from agents import RunContextWrapper, function_tool
from src.agent.context import Context
from src.utils import convert_date_format
from src.tools import load_prompt


@function_tool
async def search_sec_filings(
    ctx: RunContextWrapper[Context],
    search_query: str,
    filing_types: list[str] | None = None,
    company_name: str | None = None,
    financial_terms: list[str] | None = None,
    search_after_date: str | None = None,
    search_before_date: str | None = None,
    search_recency_filter: Literal["day", "week", "month", "year"] | None = None,
    search_context_size: Literal["low", "medium", "high"] | None = None,
    ):
    """
    Searches SEC regulatory filings (10-K, 10-Q, 8-K, etc.) for official company data. 
    Returns excerpts from filings with document types, dates, and citations.

    Args:
        search_query (required): What to find (e.g., "semiconductor supply chain risks").
        filing_types (optional): Document types - ["10-K"], ["10-Q"], ["8-K"], or combinations.
        company_name (optional): Company to focus on (e.g., "Tesla"). Omit for industry-wide search.
        financial_terms (optional): Target sections - ["earnings"], ["risk factors"], ["management discussion"], ["cash flow"].
        search_after_date (optional): Filings after date in YYYY-MM-DD format.
        search_before_date (optional): Filings before date in YYYY-MM-DD format.
        search_recency_filter (optional): Quick time filter - "day", "week", "month", "year".
        search_context_size (optional): Search depth - "low", "medium" (default), "high".
    """

    # Convert date formats for SEC API
    success, search_after_date_str = convert_date_format(search_after_date, input_format="%Y-%m-%d", output_format="%m/%d/%Y")
    if not success and search_after_date is not None:
        return {"error": f"search_after_date must be in the format YYYY-MM-DD (e.g., '2023-01-01'). Provided: {search_after_date}"}

    success, search_before_date_str = convert_date_format(search_before_date, input_format="%Y-%m-%d", output_format="%m/%d/%Y")
    if not success and search_before_date is not None:
        return {"error": f"search_before_date must be in the format YYYY-MM-DD (e.g., '2023-01-01'). Provided: {search_before_date}"}
        
    
    system_prompt = load_prompt("sec_filings.md")

    prompt = f"""Filing Types: {filing_types}
    Company Name: {company_name}
    Financial Terms: {financial_terms}
    Search Query: {search_query}"""
    
    try:
        extra_body = {
            "search_mode": "sec",
            "search_context_size": search_context_size,
        }
        
        if search_after_date_str:
            extra_body["search_after_date_filter"] = search_after_date_str
        if search_before_date_str:
            extra_body["search_before_date_filter"] = search_before_date_str
        if search_recency_filter:
            extra_body["search_recency_filter"] = search_recency_filter
            
        completion = await ctx.context.client.chat.completions.create(
            model=ctx.context.web_search_model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            extra_body=extra_body
        )
        return completion.choices[0].message.content
    except Exception as e:
        return {"error": f"Error searching SEC filings: {str(e)}"}

@function_tool
async def search_web(
    ctx: RunContextWrapper[Context],
    search_query: str,
    search_after_date: str | None = None,
    search_before_date: str | None = None,
    search_recency_filter: Literal["day", "week", "month", "year"] | None = None,
    search_context_size: Literal["low", "medium", "high"] | None = None,
    location_country: str | None = None,
    search_domain_filter: Literal["standard", "social"] = "standard",
    ) -> str:
    """
    Searches the web for news, market analysis, and current events. 
    Returns synthesized results from multiple sources with citations.

    Args:
        search_query (required): What to find (e.g., "Tesla Q4 earnings reactions").
        search_after_date (optional): Results after date in YYYY-MM-DD format.
        search_before_date (optional): Results before date in YYYY-MM-DD format.
        search_recency_filter (optional): Time filter - "day", "week", "month", "year".
        search_context_size (optional): Search depth - "low", "medium" (default), "high".
        location_country (optional): Two-letter country code (e.g., "US", "GB", "JP").
        search_domain_filter (optional): "standard" (news sites) or "social" (Reddit, Twitter, StockTwits).
    """
    
    # Convert date formats for web search API
    success, search_after_date_str = convert_date_format(search_after_date, input_format="%Y-%m-%d", output_format="%m/%d/%Y")
    if not success and search_after_date is not None:
        return {"error": f"search_after_date must be in the format YYYY-MM-DD (e.g., '2025-01-01'). Provided: {search_after_date}"}

    success, search_before_date_str = convert_date_format(search_before_date, input_format="%Y-%m-%d", output_format="%m/%d/%Y")
    if not success and search_before_date is not None:
        return {"error": f"search_before_date must be in the format YYYY-MM-DD (e.g., '2025-12-31'). Provided: {search_before_date}"}
    
    # Build extra_body with filters
    extra_body = {}
    
    # Add date filters
    if search_after_date_str:
        extra_body["search_after_date_filter"] = search_after_date_str
    if search_before_date_str:
        extra_body["search_before_date_filter"] = search_before_date_str
    if search_recency_filter:
        extra_body["search_recency_filter"] = search_recency_filter
    if search_domain_filter == "social":
        extra_body["search_domain_filter"] = ["reddit.com", "twitter.com", "stocktwits.com"]
    
    # Build web_search_options
    web_search_options = {}
    
    # Add search context size
    if search_context_size:
        web_search_options["search_context_size"] = search_context_size
    
    # Add location filter
    if location_country:
        web_search_options["user_location"] = {"country": location_country}
    
    if web_search_options:
        extra_body["web_search_options"] = web_search_options
        
    try:
        # Make the request
        completion = await ctx.context.client.chat.completions.create(
            model=ctx.context.web_search_model,
            messages=[
                {
                    "role": "system",
                    "content": load_prompt("web_search.md")
                },
                {
                    "role": "user",
                    "content": search_query
                }
            ],
            extra_body=extra_body if extra_body else None
        )
        return completion.choices[0].message.content
    
    except Exception as e:
        return {"error": f"Error searching web: {str(e)}"}


