# Telegram Repost Bot
Are you in a Telegram group with a bunch of people posting memes?\
Do they sometimes send something that's been posted before?\
If this gets your blood boiling, Repost Bot is what you need. Repost Bot keeps track of messages with pictures or URLs in them by creating a hash of them, similar to how reverse image search works.

# How to run your own instance of Repost Bot
- Create a bot by talking to [@Botfather](https://telegram.me/botfather) on Telegram.
- Ensure you have at least Python 3.8 installed on your computer.
- Clone the repo from GitHub:\
  `git clone https://github.com/sglowery/Telegram-Repost-Bot.git <FOLDER_NAME>`\
  and run `pip install -r requirements.txt` inside the folder you created (I recommend also using a virtual environment)
- Create a copy of defaultconfig.yaml, add your token from Botfather and replace any other fields you want.
  - Note: Do not use defaultconfig.yaml as your primary config.
- Run Repost Bot with the command `python main.py -c CONFIG_PATH`
- Add the bot to your group and enjoy your oasis of original content!

# If you don't want to run your own:
- Simply add [@REEEEPost Bot](https://telegram.me/reeeepost_bot) to your group! My own configuration may not be to your liking, however.

# Commands
- `/help` - Bot will reply with information on what it does and what it stores
- `/toggle [url | picture]` - Toggles tracking of the passed arguments (currently only tracks URLs and pictures)
- `/settings` - Display what the bot is tracking for the current group
- `/whitelist` - Reply to a picture or URL with this command to toggle the whitelist status of what you're replying to
- `/reset` - Only group admins and the user whose ID is set as the bot's admin can call this. Will reset a group's repost and whitelist data and revert tracking to the default settings

# Repost Bot Updates
If you want to keep up with development updates and give feedback on future improvements, check out the [Repost Bot Development News](https://t.me/repost_bot_news) channel on Telegram!