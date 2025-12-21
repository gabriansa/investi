# Investi

An autonomous AI financial analyst and trader that runs on Telegram.

→ **[gabriansa.github.io/investi](https://gabriansa.github.io/investi/)**

→ **[Telegram Bot: @investi101_bot](https://t.me/investi101_bot)**

![Investi Demo](cover.png)

## Quick Setup

### 1. Download the Project
```bash
git clone https://github.com/gabriansa/investi.git
cd investi
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Up PostgreSQL

```bash
# Install PostgreSQL
brew install postgresql@15
brew services start postgresql@15

# Create database
createdb investi
```

### 4. Set Up Environment Variables

Create a `.env` file in the root directory with the following:

```env
# LangSmith Tracing (see langsmith.com for setup)
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=investi

# OpenAI API Key (needed for LangSmith tracing)
OPENAI_API_KEY=your_openai_api_key

# Database (PostgreSQL)
DATABASE_URL=postgresql:///investi

# OpenRouter API
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

### 5. Run the Bot
```bash
python main.py
```

## API Keys Setup

To use Investi, you'll need to get API keys from a few services:

### OpenRouter
- Sign up at [openrouter.ai](https://openrouter.ai)
- Get your API key from the dashboard
- This will be set through the Telegram bot using `/set_openrouter`

### Alpaca Markets
- Create an account at [alpaca.markets](https://alpaca.markets)
- Use a **paper money account** unless you feel absolutely crazy
- Get your API keys (Key ID and Secret Key) from the dashboard
- These will be set through the Telegram bot using `/set_alpaca`

## Notes

- The project uses local PostgreSQL. If you wish you can connect this to your favorite database provider.
- Get your Telegram bot token by creating a bot with [@BotFather](https://t.me/botfather) on Telegram.

## Disclaimer

This software is for educational purposes only and does not constitute financial advice. Use at your own risk—the creators assume no liability for any losses incurred.

