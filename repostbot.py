import json
import logging
import os
from typing import Optional, List, NoReturn

from PIL import Image
from imagehash import average_hash
from telegram import Bot, Update, ChatAction, MessageEntity, Message, User, Chat, KeyboardButton, ReplyKeyboardMarkup, \
    ReplyKeyboardRemove
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, CallbackContext, ConversationHandler

import config
import strings
from config import REPOST_BOT_TOKEN

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

logger = logging.getLogger(__name__)


class RepostBot:
    RESET_CONFIRMATION_STATE = 0

    def __init__(self):
        self._check_directory()
        self.reset_conversation_states = {
            RepostBot.RESET_CONFIRMATION_STATE: [MessageHandler(Filters.text, self._handle_reset_confirmation)]
        }
        self.updater = Updater(REPOST_BOT_TOKEN, use_context=True)
        self.dp = self.updater.dispatcher
        self.dp.add_handler(MessageHandler(Filters.photo | Filters.entity("url"), self._check_potential_repost))
        self.dp.add_handler(CommandHandler("toggle", self._toggle_tracking))
        self.dp.add_handler(ConversationHandler([CommandHandler("reset", self._reset_command)], self.reset_conversation_states, fallbacks=[]))
        self.dp.add_handler(CommandHandler("help", self._repost_bot_help))
        self.dp.add_handler(CommandHandler("settings", self._display_toggle_settings))
        self.dp.add_handler(CommandHandler("whitelist", self._whitelist_command))

    def run(self):
        self.updater.start_polling()
        logger.info("bot is running")
        self.updater.idle()

    def _reset_command(self, update: Update, context: CallbackContext):
        user: User = update.message.from_user
        chat: Chat = update.message.chat
        if user.id == config.BOT_ADMIN_ID or user.id in [chat_member.user.id for chat_member in chat.get_administrators()]:
            keyboard_buttons = [[KeyboardButton("Yes"), KeyboardButton("No")]]
            keyboard_markup = ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True, selective=True)
            update.message.reply_text(strings.GROUP_REPOST_RESET_INITIAL_PROMPT,
                                      reply_to_message_id=update.message.message_id,
                                      reply_markup=keyboard_markup)
            return RepostBot.RESET_CONFIRMATION_STATE
        else:
            update.message.reply_text(strings.GROUP_REPOST_RESET_ADMIN_ONLY, quote=True)
            return ConversationHandler.END

    def _handle_reset_confirmation(self, update: Update, context: CallbackContext):
        response = self._strip_punctuation(str(update.message.text).lower())
        bot_response = strings.GROUP_REPOST_RESET_NO
        if response in ('y', 'yes', 'yeah', 'yep', 'aye', 'yis', 'yas', 'uh huh', 'sure'):
            self._reset_group_repost_data(update.message.chat.id)
            bot_response = strings.GROUP_REPOST_DATA_RESET
        update.message.reply_text(bot_response, reply_markup=ReplyKeyboardRemove(selective=True), reply_to_message_id=update.message.message_id)
        return ConversationHandler.END

    def _strip_punctuation(self, txt: str) -> str:
        return ''.join(filter(lambda l: l.lower() in 'abcdefghijklmnopqrstuvwxyz', txt))

    def _reset_group_repost_data(self, cid: str):
        group_data = self._get_group_data(cid)
        new_group_data = {"track": group_data["track"],
                          "reposts": {}
                          }
        with open(self._get_group_path(cid), 'w') as f:
            json.dump(new_group_data, f, indent=2)

    def _repost_bot_help(self, update: Update, context: CallbackContext) -> NoReturn:
        bot_name = context.bot.get_me().first_name
        context.bot.send_message(update.message.chat.id, strings.HELP_STRING.format(name=bot_name))

    def _whitelist_command(self, update: Update, context: CallbackContext) -> NoReturn:
        cid = update.message.chat.id
        reply_message = update.message.reply_to_message
        if reply_message is None:
            context.bot.send_message(cid, strings.INVALID_WHITELIST_REPLY, reply_to_message_id=update.message.message_id)
            return
        else:
            reply_id = reply_message.message_id
        with open(self._get_group_path(cid)) as f:
            group_data = json.load(f)
        self._toggle_whitelist_data(context.bot, update.message.message_id, cid, reply_id, reply_message, group_data)

    def _toggle_whitelist_data(self, bot, message_id, cid, reply_id, reply_message, group_data):
        whitelist_data = group_data.get("whitelist", list())
        keys = self._get_repost_keys(bot, reply_message)
        if keys is not None:
            for key in keys:
                whitelist_data.append(key)
            group_data["whitelist"] = whitelist_data
            with open(self._get_group_path(cid), 'w') as f:
                json.dump(group_data, f, indent=2)
            bot.send_message(cid, strings.SUCCESSFUL_WHITELIST_REPLY, reply_to_message_id=reply_id)
        else:
            bot.send_message(cid, strings.INVALID_WHITELIST_REPLY, reply_to_message_id=message_id)

    def _toggle_tracking(self, update: Update, context: CallbackContext) -> NoReturn:
        group_type = update.message.chat.type
        if group_type in ("private"):
            update.message.reply_text(strings.PRIVATE_CHAT_TOGGLE_STRING)
        else:
            cid = update.message.chat.id
            out = list()
            group_data = self._get_group_data(cid)
            toggle_data = group_data.get("track", config.DEFAULT_CALLOUT)
            for arg in ("url", "picture"):
                if arg in context.args:
                    toggle_data[arg] = not toggle_data[arg]
                    out.append(f"Tracking {arg}s: {toggle_data[arg]}")
            group_data["track"] = toggle_data
            with open(self._get_group_path(cid), 'w') as f:
                json.dump(group_data, f, indent=2)
            update.message.reply_text("\n".join(out))

    def _get_group_data(self, cid) -> dict:
        self._ensure_group_file(cid)
        with open(self._get_group_path(cid)) as f:
            data: dict = json.load(f)
        return data

    def _display_toggle_settings(self, update: Update, context: CallbackContext) -> NoReturn:
        cid = update.message.chat.id
        self._ensure_group_file(cid)
        with open(self._get_group_path(cid)) as f:
            group_toggles = json.load(f).get("track")
        out = "\n".join(f"Tracking {k}s: {v}" for k, v in group_toggles.items())
        context.bot.send_message(cid, out)

    # <group_id>.txt maps an image hash or url to a list of message ids that contain an image with that hash or url
    def _get_group_path(self, group_id):
        return f"{config.GROUP_REPOST_PATH}/{group_id}.json"

    def _check_potential_repost(self, update: Update, context: CallbackContext) -> NoReturn:
        bot = context.bot
        cid, chat_type, mid = update.message.chat.id, update.message.chat.type, update.message.message_id
        self._ensure_group_file(cid)
        potential_repost_keys = self._get_repost_keys(bot, update.message)
        if chat_type in ("private", "group") and update.message.forward_from is None and potential_repost_keys is not None:
            for key in potential_repost_keys:
                if self._is_repost(cid, key, mid):
                    self._reeeeeeeepost(bot, update, key, mid, cid)

    def _ensure_group_file(self, cid: int) -> NoReturn:
        try:
            with open(self._get_group_path(cid)):
                pass
        except FileNotFoundError:
            logger.info("group has no file; making one")
            with open(self._get_group_path(cid), 'w') as f:
                json.dump({"track": config.DEFAULT_CALLOUT, "reposts": {}}, f, indent=2)

    def _get_repost_keys(self, bot: Bot, message: Message) -> Optional[List[str]]:
        keys = list()
        entities = message.parse_entities(types=[MessageEntity.URL])
        with open(self._get_group_path(message.chat.id)) as f:
            group_toggles = json.load(f).get("track")
        if message.photo and group_toggles["picture"]:
            photo = message.photo[-1]
            path = f"{photo.file_id}.jpg"
            logger.info("getting file...")
            bot.get_file(photo).download(path)
            logger.info("done")
            keys.append(str(average_hash(Image.open(path), hash_size=24)))
            os.remove(path)
            return keys
        elif len(entities) and group_toggles["url"]:
            for entity in entities:
                keys.append(str(hash(message.text[entity.offset: entity.offset + entity.length])))
            return keys
        else:
            return None

    def _is_repost(self, group_id: int, key: str, message_id: int) -> bool:
        result = False
        group_path = self._get_group_path(group_id)
        with open(group_path, 'r') as f:
            group_reposts = json.load(f)
        if group_reposts["reposts"].get(key, None) is None:
            logger.info("new picture or url detected")
            group_reposts["reposts"].update({key: [message_id]})
        else:
            whitelist_data = group_reposts.get("whitelist", list())
            if key not in whitelist_data:
                logger.info("REPOST DETECTED REEEE")
                group_reposts["reposts"].get(key).append(message_id)
                result = True
            else:
                logger.info("Key is whitelisted; doing nothing")
            group_reposts["whitelist"] = whitelist_data
        with open(group_path, 'w') as f:
            json.dump(group_reposts, f, indent=2)
        return result

    def _reeeeeeeepost(self, bot, update, key, mid, cid):
        name = update.message.from_user.first_name
        bot.send_chat_action(cid, ChatAction.TYPING)
        bot.send_message(cid, strings.REPOST_ALERT_STRING, reply_to_message_id=mid)
        for i, repost_msg in enumerate(self._get_all_but_last_reposts(cid, key)):
            bot.send_chat_action(cid, ChatAction.TYPING)
            if i == 0:
                msg = strings.REPOST_NOTIFIERS[0]
            else:
                msg = strings.REPOST_NOTIFIERS[1]
            bot.send_message(cid, msg, reply_to_message_id=repost_msg)
        bot.send_chat_action(cid, ChatAction.TYPING)
        bot.send_message(cid, strings.REPOST_NOTIFIERS[2].format(name=name.upper()))

    def _get_group_repost_data(self):
        pass

    def _get_all_but_last_reposts(self, group_id: int, key: str) -> List[str]:
        return self._get_repost_messages(group_id, key)[:-1]

    def _get_repost_messages(self, group_id: int, key: str) -> List[str]:
        with open(self._get_group_path(group_id), 'r') as f:
            reposts = json.load(f).get("reposts")
        return reposts[key]

    def _check_directory(self) -> NoReturn:
        if not os.path.exists(config.GROUP_REPOST_PATH):
            os.makedirs(config.GROUP_REPOST_PATH)


if __name__ == "__main__":
    rpb = RepostBot()
    rpb.run()
