from typing import Literal

ROLES = ["portfolio_manager", "analyst"]
RoleLiteral = Literal.__getitem__(tuple(ROLES))

TOPICS_WITH_DESCRIPTIONS = {
    "Research & Analysis": {
        "IDEA": "Initial idea generation - why looking at this, source attribution, hypothesis, priority level.",
        "RESEARCH": "General research and investigation - broad information gathering, sector research, market trends, preliminary analysis.",
        "BUSINESS_REVIEW": "Business model deep-dive - how they make money, moat, unit economics, competitive advantages.",
        "FINANCIAL_REVIEW": "Financial performance analysis - revenue/margin trends, cash flow, balance sheet, accounting quality.",
        "COMPETITIVE_VIEW": "Competitive positioning - vs competitors, market share dynamics, who's winning/losing and why.",
        "VALUATION": "Valuation analysis - fair value estimate, DCF/comps, upside/downside scenarios, price targets.",
        "MACRO_CONTEXT": "Economic/sector backdrop - cycle position, rates impact, sector trends, policy environment.",
    },
    "Risk & Opportunity Assessment": {
        "RISK_FACTORS": "Downside risk analysis - thesis killers, what could go wrong, red flags, stop loss levels.",
        "CATALYSTS": "Upside drivers - events that could drive outperformance, inflection points, optionality, timing.",
        "MANAGEMENT_VIEW": "Management quality assessment - execution track record, capital allocation, alignment, culture.",
    },
    "Decision Points": {
        "ENTRY_DECISION": "Buy decision documentation - why now, entry price, position size, conviction level, base/bull/bear cases, sell criteria.",
        "EXIT_DECISION": "Sell decision documentation - why selling, what got right/wrong, lessons learned, final return.",
        "SIZING_DECISION": "Position sizing logic - why this size, concentration considerations, plan to add/trim.",
    },
    "Ongoing Monitoring": {
        "POSITION_CHECK": "Routine position review - thesis status (intact/improving/deteriorating), new developments, action needed.",
        "EVENT_UPDATE": "Specific event documentation - earnings, news, announcements and their impact on thesis.",
        "TECHNICAL_VIEW": "Price action analysis - support/resistance levels, entry/exit timing, stop losses.",
    },
    "Portfolio Level": {
        "ALLOCATION": "Portfolio construction decisions - sector weights, style exposure, allocation shifts and reasoning.",
        "RISK_MANAGEMENT": "Portfolio risk monitoring - concentration, correlation, hedging strategy, risk limits.",
        "PERFORMANCE": "Performance review and attribution - returns vs benchmark, what worked/didn't, insights.",
    },
    "Learning & Improvement": {
        "MISTAKE": "Explicit mistake analysis - what went wrong, what missed, process vs outcome, prevention rules.",
        "PROCESS_NOTE": "Investment process improvements - patterns noticed, behavioral biases, checklist additions, rule changes.",
    },
}

# Dynamically create list and Literal from TOPICS_WITH_DESCRIPTIONS
TOPICS = [topic for category in TOPICS_WITH_DESCRIPTIONS.values() for topic in category.keys()]
TopicLiteral = Literal.__getitem__(tuple(TOPICS))

TOPICS_STRING = "\n\n".join([f"{category}:\n" + "\n".join([f"    {topic}: {description}" for topic, description in topics.items()]) for category, topics in TOPICS_WITH_DESCRIPTIONS.items()])
