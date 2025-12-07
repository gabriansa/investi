"""
Input guardrails for the Investi agent system.
"""
from pydantic import BaseModel
from agents import Agent, Runner, input_guardrail, GuardrailFunctionOutput, RunContextWrapper, TResponseInputItem, OpenAIChatCompletionsModel
from src.agent.context import Context


class PortfolioRelevanceCheck(BaseModel):
    is_portfolio_relevant: bool
    reasoning: str


def create_portfolio_guardrail(instructions: str, model: str, openai_client):
    """
    Factory function to create a portfolio relevance guardrail.
    
    Args:
        instructions: The guardrail prompt instructions
        model: Model name to use for the guardrail
        openai_client: OpenAI client instance
        
    Returns:
        The guardrail function with the agent bound via closure
    """
    guardrail_agent = Agent(
        name="Portfolio Relevance Guardrail",
        instructions=instructions,
        output_type=PortfolioRelevanceCheck,
        model=OpenAIChatCompletionsModel(model=model, openai_client=openai_client)
    )
    
    @input_guardrail
    async def portfolio_relevance_guardrail(
        ctx: RunContextWrapper[Context], agent: Agent, input: str | list[TResponseInputItem]
    ) -> GuardrailFunctionOutput:
        result = await Runner.run(guardrail_agent, input, context=ctx.context)
        
        return GuardrailFunctionOutput(
            output_info=result.final_output,
            tripwire_triggered=not result.final_output.is_portfolio_relevant,
        )
    
    return portfolio_relevance_guardrail

