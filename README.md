# Telegram-Repost-Bot
Tracks images and URLs sent in groups on Telegram and calls out reposts.

# Dependencies
Requires the `imagehash` and `python-telegram-bot` libraries. The latter should come with the `telegram` library.
Made with Python 3.7

# How to Use
- Create a bot by talking to [@Botfather](https://telegram.me/botfather) on Telegram.
- Clone or download this repo and run `setup.py`
- Rename `config_example.yaml` to `config.yaml` and replace any placeholder fields with your own information or change the others as you want
- Run `repostbot.py` with the command `python repostbot.py -c CONFIG_PATH`
- Add the bot to your group and enjoy your OC oasis

# Commands
- `/help` - Bot will reply with information on what it does and what it stores
- `/toggle [url | picture]` - Toggles tracking of the passed arguments (currently only tracks URLs and pictures)
- `/settings` - Display what the bot is tracking for the current group
- `/whitelist` - Use this command while replying to a message that contains an image or URL you want to whitelist
- `/reset` - Only group admins and the user whose ID is set as the bot's admin can call this. Will reset a group's repost and whitelist data and revert tracking to the default settings