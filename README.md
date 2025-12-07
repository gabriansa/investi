# Investi

An autonomous AI financial analyst and trader that runs on Telegram.

→ **[gabriansa.github.io/investi](https://gabriansa.github.io/investi/)**

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

### 3. Set Up Environment Variables

Create a `.env` file in the root directory with the following:

```env
# LangSmith Tracing (see langsmith.com for setup)
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=investi

# OpenAI API Key (needed for LangSmith tracing)
OPENAI_API_KEY=your_openai_api_key

# Database (local SQLite database)
DATABASE_PATH=data/investi.db

# OpenRouter API
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

### 4. Run the Bot
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

- The project uses a local SQLite database by default. If you want to change this, you'll need to modify the database configuration.
- You can run this 24/7 on a server, Raspberry Pi, or any machine with Python.
- Get your Telegram bot token by creating a bot with [@BotFather](https://t.me/botfather) on Telegram.

## Telegram Commands

Once running, you can use these commands in Telegram:

- `/start` - Register and get started
- `/set_alpaca` - Set your Alpaca API credentials
- `/set_openrouter` - Set your OpenRouter API key
- `/status` - Check account and portfolio status
- `/delete_account` - Delete your account and data

## Disclaimer

This software is for educational purposes only and does not constitute financial advice. Use at your own risk—the creators assume no liability for any losses incurred.
