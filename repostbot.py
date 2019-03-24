from imagehash import average_hash
from PIL import Image
from telegram import Bot, Update, ChatAction, MessageEntity, Message
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
from bot_token import REPOST_BOT_TOKEN
from typing import Optional, List, NoReturn
import os
import json
import config


# <group_id>.txt maps an image hash or url to a list of message ids that contain an image with that hash or url
def get_group_path(group_id):
    return f"{config.GROUP_REPOST_PATH}/{group_id}.json"


def is_repost(group_id: int, key: str, message_id: int) -> bool:
    result = False
    group_path = get_group_path(group_id)
    with open(group_path, 'r') as f:
        group_reposts = json.load(f)
    if group_reposts.get(key, None) is None:
        print("new picture or url detected")
        group_reposts[key] = [message_id]
    else:
        whitelist_data = group_reposts.get("whitelist", list())
        if key not in whitelist_data:
            print("REPOST DETECTED REEEE")
            group_reposts[key].append(message_id)
            result = True
        else:
            print("Key is whitelisted; doing nothing")
        group_reposts["whitelist"] = whitelist_data
    with open(group_path, 'w') as f:
        json.dump(group_reposts, f, indent=2)
    return result


def get_repost_messages(group_id: int, key: str) -> List[str]:
    with open(get_group_path(group_id), 'r') as f:
        reposts = json.load(f)
    return reposts[key]


def get_all_but_last_reposts(group_id: int, key: str) -> List[str]:
    return get_repost_messages(group_id, key)[:-1]


def ensure_group_file(cid: int) -> NoReturn:
    try:
        with open(get_group_path(cid)):
            pass
    except FileNotFoundError:
        print("group has no file; making one")
        with open(get_group_path(cid), 'w') as f:
            json.dump({"track": config.DEFAULT_CALLOUT}, f, indent=2)


def get_keys(bot: Bot, message: Message) -> Optional[List[str]]:
    keys = list()
    entities = message.parse_entities(types=[MessageEntity.URL])
    with open(get_group_path(message.chat.id)) as f:
        group_toggles = json.load(f).get("track")
    if message.photo and group_toggles["picture"]:
        photo = message.photo[-1]
        photo_id = photo.file_id
        path = f"{photo_id}.jpg"
        print("getting file...")
        bot.get_file(photo).download(path)
        print("done")
        image_hash = str(average_hash(Image.open(path)))
        os.remove(path)
        keys.append(image_hash)
        return keys
    elif len(entities) and group_toggles["url"]:
        for entity in entities:
            keys.append(str(message.text[entity.offset: entity.offset + entity.length]))
        return keys
    else:
        return None


def receive_repostable(bot: Bot, update: Update) -> NoReturn:
    cid = update.message.chat.id
    chat_type = update.message.chat.type
    mid = update.message.message_id
    ensure_group_file(cid)
    keys = get_keys(bot, update.message)
    if chat_type in ("private", "group") and update.message.forward_from is None and keys is not None:
        for key in keys:
            if is_repost(cid, key, mid):
                name = update.message.from_user.first_name
                bot.send_chat_action(cid, ChatAction.TYPING)
                bot.send_message(cid, config.REPOST_ALERT_STRING, reply_to_message_id=mid)
                for i, repost_msg in enumerate(get_all_but_last_reposts(cid, key)):
                    bot.send_chat_action(cid, ChatAction.TYPING)
                    if i == 0:
                        msg = config.REPOST_NOTIFIERS[0]
                    else:
                        msg = config.REPOST_NOTIFIERS[1]
                    bot.send_message(cid, msg, reply_to_message_id=repost_msg)
                bot.send_chat_action(cid, ChatAction.TYPING)
                bot.send_message(cid, config.REPOST_NOTIFIERS[2].format(name=name.upper()))


def whitelist(bot: Bot, update: Update) -> NoReturn:
    cid = update.message.chat.id
    reply_message = update.message.reply_to_message
    if reply_message is None:
        bot.send_message(cid, config.INVALID_WHITELIST_REPLY, reply_to_message_id=update.message.message_id)
        return
    else:
        reply_id = reply_message.message_id
    with open(get_group_path(cid)) as f:
        group_data = json.load(f)
    whitelist_data = group_data.get("whitelist", list())
    keys = get_keys(bot, reply_message)
    if keys is not None:
        for key in keys:
            whitelist_data.append(key)
        group_data["whitelist"] = whitelist_data
        with open(get_group_path(cid), 'w') as f:
            json.dump(group_data, f)
        bot.send_message(cid, config.SUCCESSFUL_WHITELIST_REPLY, reply_to_message_id=reply_id)
    else:
        bot.send_message(cid, config.INVALID_WHITELIST_REPLY, reply_to_message_id=update.message.message_id)


def toggle_tracking(bot: Bot, update: Update, args: list) -> NoReturn:
    group_type = update.message.chat.type
    if "private" in group_type:
        update.message.reply_text(config.PRIVATE_CHAT_TOGGLE_STRING)
    else:
        cid = update.message.chat.id
        out = list()
        ensure_group_file(cid)
        with open(get_group_path(cid)) as f:
            group_data = json.load(f)
        toggle_data = group_data.get("track", config.DEFAULT_CALLOUT)
        if "url" in args:
            toggle_data["url"] = not toggle_data["url"]
            out.append(f"Tracking URLs: {toggle_data['url']}")
        if "picture" in args:
            toggle_data["picture"] = not toggle_data["picture"]
            out.append(f"Tracking pictures: {toggle_data['picture']}")
        group_data["track"] = toggle_data
        with open(get_group_path(cid), 'w') as f:
            json.dump(group_data, f, indent=2)
        update.message.reply_text("\n".join(out))


def display_toggle_settings(bot: Bot, update: Update) -> NoReturn:
    cid = update.message.chat.id
    ensure_group_file(cid)
    with open(get_group_path(cid)) as f:
        group_toggles = json.load(f).get("track")
    out = "\n".join(f"Tracking {k}s: {v}" for k, v in group_toggles.items())
    bot.send_message(cid, out)


def check_directory() -> NoReturn:
    if not os.path.exists(config.GROUP_REPOST_PATH):
        os.makedirs(config.GROUP_REPOST_PATH)


def repost_bot_help(bot: Bot, update: Update) -> NoReturn:
    bot_name = bot.get_me().first_name
    bot.send_message(update.message.chat.id, config.HELP_STRING.format(name=bot_name))


def main() -> NoReturn:
    check_directory()
    updater = Updater(REPOST_BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.photo | Filters.entity("url"), receive_repostable))
    dp.add_handler(CommandHandler("toggle", toggle_tracking, pass_args=True))
    dp.add_handler(CommandHandler("help", repost_bot_help))
    dp.add_handler(CommandHandler("settings", display_toggle_settings))
    dp.add_handler(CommandHandler("whitelist", whitelist))
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
