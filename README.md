# Telegram Repost Bot

Are you in a Telegram group with a bunch of people posting memes or other content?\
Do they sometimes send something that's been posted before?\
If this gets your blood boiling, Repost Bot is what you need. Repost Bot keeps track of messages with pictures or URLs in them by creating a hash of them, similar to how reverse image search works.
If someone posts unoriginal content, they will be called out and, ideally, be very embarrassed.

# How to run your own instance of Repost Bot

- Create a bot by talking to [@BotFather](https://telegram.me/botfather) on Telegram.
- Use BotFather to turn off privacy mode -- this is required since RepostBot needs to check messages as they come in.
- Ensure you have at least Python 3.8 installed on your computer.
- Clone the repo from GitHub and install the dependencies:\
  `git clone https://github.com/sglowery/Telegram-Repost-Bot.git <FOLDER_NAME>`\
  `cd <FOLDER_NAME>`\
  `pip install -r requirements.txt` inside the folder you created (I recommend doing this in a virtual environment)
- Create a copy of defaultconfig.yaml, name it whatever you want, add your token from BotFather and replace any of the string values you want.
  - Note: Do not use defaultconfig.yaml as your primary config; it will receive updates if new configuration options and strings are added.
- Run Repost Bot with the command `python main.py -c CONFIG_FILE_PATH`
- Add the bot to your group and enjoy your oasis of original content!

# If you don't want to run your own:

- Simply add [@REEEEPost Bot](https://telegram.me/reeeepost_bot) to your group! My own configuration may not be to your liking, however.

# Commands

- `/help` - Bot will reply with information on what it does and what it stores
- `/toggle` - Toggles tracking of individual entity types (can toggle multiple at a time)
  - Valid arguments: `picture`, `url`
- `/settings` - Display what the bot is tracking for the current group
- `/whitelist` - Reply to a picture or URL with this command to toggle the whitelist status of what you're replying to
- `/reset` - Only group admins and the user whose ID is set as the bot's admin can call this. Will reset a group's repost and whitelist data and revert tracking to the default settings
- `/stats` - Show some basic repost stats in the group

# How To Use

- ## Groups

  - Add the bot to your group.
  - Use commands to interact with it.
  - Use the `/settings` command to see what's being tracked, and use `/toggle` to change the settings if desired.
  - Admins can `/reset` the group's repost data, clearing it entirely.
  - Is RepostBot calling out something that you don't want it to? Reply to the message containing what you don't want called out anymore and use the `/whitelist` command.
    - Use this command again to remove it from the whitelist.
  - Want to know some basic stats about the group's repost data? Use the `/stats` command.
  - RepostBot has anti-flood measures implemented for commands and repost callouts. If it appears the bot is unresponsive, wait a minute and try again. If it's still not responsive, try a command like `/help`. If that doesn't work, it's likely the bot is down.
  
- ## Channels

  - RepostBot can be added to channels, but has limited functionality:
    - It can still track pictures and URLs and abide by the default settings for tracking callouts.
    - It can _not_ receive commands

# Repost Bot Updates

If you want to keep up with development updates and give feedback on future improvements, check out the [Repost Bot Development News](https://t.me/repost_bot_news) channel on Telegram!