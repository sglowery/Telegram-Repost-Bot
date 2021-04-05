# Telegram Repost Bot
Are you in a Telegram group with a bunch of people posting memes?\
Do they sometimes send something that's been posted before?\
If this gets your blood boiling, Repost Bot is what you need. Repost Bot keeps track of messages with pictures or URLs in them by creating a hash\
of them, similar to how reverse image search works.

# Dependencies
Requires the `imagehash` and `python-telegram-bot` libraries. The latter should come with the `telegram` library.
Made with Python 3.8

# How to run your own instance of Repost Bot
- Create a bot by talking to [@Botfather](https://telegram.me/botfather) on Telegram.
- Clone or download this repo and run `setup.py` (I recommend using a virtual environment, but it's not required)
- Create a copy of defaultconfig.yaml, add your token from Botfather and replace any other fields you want
  - Note: Do not use defaultconfig.yaml as your primary config
- Run `repostbot.py` with the command `python repostbot.py -c CONFIG_PATH`
- Add the bot to your group and enjoy your oasis of original content

# If you don't want to run your own:
- Simply add [@REEEEPost Bot](https://telegram.me/reeeepost_bot) to your group! My own configuration may not be to your liking, however.

# Commands
- `/help` - Bot will reply with information on what it does and what it stores
- `/toggle [url | picture]` - Toggles tracking of the passed arguments (currently only tracks URLs and pictures)
- `/settings` - Display what the bot is tracking for the current group
- `/whitelist` - Reply to a picture or URL with this command to toggle the whitelist status of what you're replying to
- `/reset` - Only group admins and the user whose ID is set as the bot's admin can call this. Will reset a group's repost and whitelist data and revert tracking to the default settings
