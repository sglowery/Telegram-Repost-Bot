# Telegram-Repost-Bot
Tracks images sent in groups on Telegram and calls out reposts.

# Dependencies
Requires the `imagehash` and `python-telegram-bot` libraries. The latter should come with the `telegram` library.
Made with Python 3.7

# How to Use
- Create a bot by talking to [@Botfather](https://telegram.me/botfather) on Telegram.
- `config.py` allows you to set the bot's responses when a repost is detected or a user types /help
- Rename `bot_token_example.py` to `bot_token.py` and paste the token from the Botfather into `REPOST_BOT_TOKEN` field's value
- Run `repostbot.py` and add your bot to your group!
