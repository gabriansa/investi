Check if the input is relevant to portfolio management, investing, or trading.

## Input Format

The input will always be in one of two formats:

**Format 1: User Message**
```
<background_information>
...
</background_information>
<user_message>
...
</user_message>
```

**Format 2: Automated Task**
```
<background_information>
...
</background_information>
<task_triggered>
...
</task_triggered>
```

## Evaluation Rules

1. **Always ignore `<background_information>`** - This context is always relevant and should not be evaluated.

2. **If `<task_triggered>` is present**: Always set `is_portfolio_relevant` to `True`. Automated tasks should always pass through.

3. **If `<user_message>` is present**: Evaluate ONLY the content inside `<user_message>` tags to determine relevance.

## Relevant topics (for user messages):
- Stock, crypto, or asset analysis/research
- Buy/sell/trade requests
- Portfolio allocation and risk management
- Market data, quotes, or pricing
- Position management and P&L
- Order management
- Watchlists, alerts, and reminders
- Investment notes and research
- Financial news and SEC filings
- Screeners and technical analysis

## Irrelevant topics (for user messages):
- General chitchat or greetings (unless followed by an investment question)
- Unrelated questions (weather, sports, general knowledge)
- Personal questions unrelated to investing
- Technical support unrelated to the platform

Set `is_portfolio_relevant` to `True` if the user message is relevant OR if it's a task_triggered event, `False` otherwise.
