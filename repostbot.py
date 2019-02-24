from imagehash import average_hash
from PIL import Image
from telegram import Bot, Update, ChatAction, MessageEntity
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
from bot_token import TEST_REPOST_BOT_TOKEN
import os
import json
import config
import logging


# <group_id>.txt maps an image hash or url to a list of message ids that contain an image with that hash or url
def get_group_path(group_id):
    return f"{config.GROUP_REPOST_PATH}/{group_id}.txt"


def is_repost(group_id: int, key: str, message_id: int) -> bool:
    result = False
    group_path = get_group_path(group_id)
    try:
        with open(group_path, 'r') as f:
            group_reposts = json.load(f)
        if group_reposts.get(key, None) is None:
            print("new picture or url detected")
            group_reposts[key] = [message_id]
        else:
            print("REPOST DETECTED REEEE")
            group_reposts[key].append(message_id)
            result = True
        with open(group_path, 'w') as f:
            json.dump(group_reposts, f, indent=4)
    except FileNotFoundError:
        print(f"new group found, creating {group_id}.txt and instantiating repost data")
        with open(group_path, 'w') as file:
            json.dump({key: [message_id]}, file, indent=4)
    return result


def get_repost_messages(group_id: int, key: str) -> list:
    with open(get_group_path(group_id), 'r') as f:
        reposts = json.load(f)
    return reposts[key]


def get_all_but_last_reposts(group_id: int, key: str) -> list:
    return get_repost_messages(group_id, key)[:-1]


def get_image_key(bot: Bot, update: Update) -> str:
    photo = update.message.photo[-1]
    photo_id = photo.file_id
    path = f"{photo_id}.jpg"
    print("getting file...")
    bot.get_file(photo).download(path)
    print("done")
    image_hash = str(average_hash(Image.open(path)))
    os.remove(path)
    return image_hash


def get_url_key(update: Update):
    print("getting url key")
    entity = update.message.entities[0]
    key = str(hash(update.message.text[entity.offset: entity.offset + entity.length]))
    print(f"key:{key}")
    return key


def receive_repostable(bot: Bot, update: Update):
    cid = update.message.chat.id
    chat_type = update.message.chat.type
    if chat_type in "test":
        bot.send_message(cid, config.PRIVATE_CHAT_STRING)
    elif chat_type in ("private", "group", "supergroup") and update.message.forward_from is None:
        message_id = update.message.message_id
        if update.message.photo:
            print("picture message found")
            key = get_image_key(bot, update)
        else:  # update.message.parse_entities(types=Filters.entity("url")):
            print("url found")
            key = get_url_key(update)
        if is_repost(cid, key, message_id):
            print("REPOST!!!")
            bot.send_chat_action(cid, ChatAction.TYPING)
            update.message.reply_text(config.REPOST_ALERT_STRING)
            for i, repost_msg in enumerate(get_all_but_last_reposts(cid, key)):
                bot.send_chat_action(cid, ChatAction.TYPING)
                if i == 0:
                    msg = config.REPOST_NOTIFIERS[0]
                else:
                    msg = config.REPOST_NOTIFIERS[1]
                bot.send_message(cid, msg, reply_to_message_id=repost_msg)
            bot.send_message(cid, config.REPOST_NOTIFIERS[2],
                             reply_to_message_id=message_id)
        else:
            print("url or picture is not repost")
    else:
        pass


def check_directory() -> None:
    if not os.path.exists(config.GROUP_REPOST_PATH):
        os.makedirs(config.GROUP_REPOST_PATH)


def repost_bot_help(bot: Bot, update: Update) -> None:
    bot_name = bot.get_me().first_name
    bot.send_message(update.message.chat.id, config.HELP_STRING.format(name=bot_name))


def main() -> None:
    check_directory()
    updater = Updater(TEST_REPOST_BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.photo | Filters.entity("url"), receive_repostable))
    # dp.add_handler(MessageHandler(Filters.entity, receive_url))
    dp.add_handler(CommandHandler("help", repost_bot_help))
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
