# Cheero Bot

A Telegram bot that fetches Meta (Facebook) ad insights and reports campaign performance with action-specific metrics.

## Features

- Fetches last 7 days Meta ad campaign insights
- Calculates cost per install, cost per message, cost per like/follow
- Sends formatted reports to Telegram group

## Deployment

### Local Development

1. Clone repo and create `.env`:
   ```bash
   cp .env.example .env
   ```

2. Add your credentials to `.env`:
   ```
   META_ACCESS_TOKEN=your_token
   META_AD_ACCOUNT_ID=act_xxxxx
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

3. Install and run:
   ```bash
   pip install -r requirements.txt
   python cheero_bot.py
   ```

### Railway Deployment

1. Connect this repo to Railway
2. Add environment variables (same as `.env`):
   - `META_ACCESS_TOKEN`
   - `META_AD_ACCOUNT_ID`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

3. Railway will auto-detect `Procfile` and run: `python cheero_bot.py`

### Scheduling

To run daily reports, set up a Railway Cron Job that triggers `python cheero_bot.py` at your preferred time.

## Files

- `cheero_bot.py` - Main bot logic
- `meta_test.py` - Quick test for Meta API
- `requirements.txt` - Python dependencies
- `Procfile` - Railway worker process definition
- `.env.example` - Environment variables template
