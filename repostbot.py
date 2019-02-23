from imagehash import average_hash
from PIL import Image
from telegram import Bot, Update
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
from bot_token import REPOST_BOT_TOKEN
import os
import json
import config
import logging


# TODO: stats on who does the most reposts, most reposted image, repost-to-original ratio


# <group_id>.txt maps an image hash to a list of message ids that contain an image with that hash
def get_group_path(group_id):
    return f"{config.GROUP_REPOST_PATH}/{group_id}.txt"


def is_repost(group_id, image_hash, message_id):
    result = False
    group_path = get_group_path(group_id)
    try:
        with open(group_path, 'r') as f:
            group_reposts = json.load(f)
        if group_reposts.get(image_hash, None) is None:
            print("new picture detected")
            group_reposts[image_hash] = [message_id]
        else:
            print("REPOST DETECTED REEEE")
            group_reposts[image_hash].append(message_id)
            result = True
        with open(group_path, 'w') as f:
            json.dump(group_reposts, f, indent=4)
    except FileNotFoundError:
        print(f"new group found, creating {group_id}.txt and instantiating repost data")
        with open(group_path, 'w') as file:
            json.dump({image_hash: [message_id]}, file, indent=4)
    return result


def get_repost_messages(group_id, image_hash):
    with open(get_group_path(group_id), 'r') as f:
        reposts = json.load(f)
    return reposts[image_hash]


def get_all_but_last_reposts(group_id, image_hash):
    return get_repost_messages(group_id, image_hash)[:-1]


def receive_image(bot: Bot, update: Update):
    cid = update.message.chat.id
    chat_type = update.message.chat.type
    if chat_type in "private":
        bot.send_message(cid, config.PRIVATE_CHAT_STRING)
    elif chat_type in ("group", "supergroup"):
        print("picture message found")
        message_id = update.message.message_id
        photo = update.message.photo[-1]
        photo_id = photo.file_id
        path = f"{photo_id}.jpg"
        print("getting file...")
        bot.get_file(photo).download(path)
        print("done")
        image_hash = str(average_hash(Image.open(path)))
        os.remove(path)
        if is_repost(cid, image_hash, message_id):
            print("REPOST!!!")
            update.message.reply_text(config.REPOST_ALERT_STRING)
            for i, repost_msg in enumerate(get_all_but_last_reposts(cid, image_hash)):
                if i == 0:
                    msg = config.REPOST_NOTIFIERS[0]
                else:
                    msg = config.REPOST_NOTIFIERS[1]
                bot.send_message(cid, msg, reply_to_message_id=repost_msg)
            bot.send_message(cid, config.REPOST_NOTIFIERS[2],
                             reply_to_message_id=message_id)
        else:
            print("picture is not repost")
    else:
        pass


def check_directory():
    if os.path.exists(config.GROUP_REPOST_PATH):
        return
    else:
        os.makedirs(config.GROUP_REPOST_PATH)


def repost_bot_help(bot: Bot, update: Update):
    bot_name = bot.get_me().first_name
    bot.send_message(update.message.chat.id, config.HELP_STRING.format(name=bot_name))


def main():
    check_directory()
    updater = Updater(REPOST_BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.photo, receive_image))
    dp.add_handler(CommandHandler("help", repost_bot_help))
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
