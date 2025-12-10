from typing import Literal

ROLES = ["portfolio_manager", "analyst"]
RoleLiteral = Literal.__getitem__(tuple(ROLES))

TOPICS_WITH_DESCRIPTIONS = {
    "IDEA": "Initial idea generation, screening results, why investigating",
    "RESEARCH": "Company deep-dive (business, financials, competitive position, management quality)",
    "THESIS": "Investment case with valuation, catalysts, risks, conviction level",
    "DECISION": "Entry/exit decisions with rationale, sizing logic, price/timing",
    "MONITORING": "Position reviews, event updates, thesis tracking",
    "PORTFOLIO": "Allocation, risk management, performance attribution",
    "TECHNICAL": "Price action, support/resistance, entry/exit timing",
    "MACRO": "Economic backdrop, sector trends, policy environment",
    "LEARNING": "Mistakes, process improvements, behavioral patterns",
    "PLANNING": "Multi-step workflows, action items, coordination",
}

# Create list and Literal from TOPICS_WITH_DESCRIPTIONS
TOPICS = list(TOPICS_WITH_DESCRIPTIONS.keys())
TopicLiteral = Literal.__getitem__(tuple(TOPICS))
