# Telegram-Repost-Bot
Tracks images and URLs sent in groups on Telegram and calls out reposts.

# Dependencies
Requires the `imagehash` and `python-telegram-bot` libraries. The latter should come with the `telegram` library.
Made with Python 3.7

# How to run your own instance of Repost Bot
- Create a bot by talking to [@Botfather](https://telegram.me/botfather) on Telegram.
- Clone or download this repo and run `setup.py`
- Rename `config_example.yaml` to `config.yaml` and replace any placeholder fields with your own information or change the others as you want
- Run `repostbot.py` with the command `python repostbot.py -c CONFIG_PATH`
- Add the bot to your group and enjoy your OC oasis

# If you don't want to run your own:
- Simply add [@REEEEPost Bot](https://telegram.me/reeeepost_bot) to your group!

# Commands
- `/help` - Bot will reply with information on what it does and what it stores
- `/toggle [url | picture]` - Toggles tracking of the passed arguments (currently only tracks URLs and pictures)
- `/settings` - Display what the bot is tracking for the current group
- `/whitelist` - Reply to a picture or URL with this command to toggle the whitelist status of what you're replying to
- `/reset` - Only group admins and the user whose ID is set as the bot's admin can call this. Will reset a group's repost and whitelist data and revert tracking to the default settings
