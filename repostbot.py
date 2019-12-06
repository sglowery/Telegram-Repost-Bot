import argparse
import logging
import random
from typing import Dict
from typing import List
from typing import NoReturn

import yaml
from telegram import Chat
from telegram import ChatAction
from telegram import KeyboardButton
from telegram import ReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove
from telegram import Update
from telegram import User
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

from repostbottypes import ConversationState
from repostbottypes import RepostSet
from repostitory import Repostitory
from whiteliststatus import WhitelistAddStatus

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

logger = logging.getLogger(__name__)


class RepostBot:
    RESET_CONFIRMATION_STATE = 0

    def __init__(self, token: str, strings: Dict[str, str], admin_id: int, repostitory: Repostitory):
        self.token = token
        self.admin_id = admin_id
        self.strings = strings
        self.repostitory = repostitory

        reset_conversation_states = {
            RepostBot.RESET_CONFIRMATION_STATE: [MessageHandler(Filters.text, self._handle_reset_confirmation)]
        }

        self.updater = Updater(self.token, use_context=True)
        self.dp = self.updater.dispatcher
        self.dp.add_handler(MessageHandler(Filters.photo | Filters.entity("url"), self._check_potential_repost))
        self.dp.add_handler(CommandHandler("toggle", self._toggle_tracking))
        self.dp.add_handler(ConversationHandler([CommandHandler("reset", self._reset_prompt_from_command)],
                                                reset_conversation_states, fallbacks=[]))
        self.dp.add_handler(CommandHandler("help", self._repost_bot_help))
        self.dp.add_handler(CommandHandler("settings", self._display_toggle_settings))
        self.dp.add_handler(CommandHandler("whitelist", self._whitelist_command))

    def run(self) -> NoReturn:
        self.updater.start_polling()
        logger.info("bot is running")
        self.updater.idle()

    def _reset_prompt_from_command(self, update: Update, context: CallbackContext) -> ConversationState:
        user: User = update.message.from_user
        chat: Chat = update.message.chat
        if user.id == self.admin_id or user.id in [chat_member.user.id for chat_member in chat.get_administrators()]:
            keyboard_buttons = [[KeyboardButton("Yes"), KeyboardButton("No")]]
            keyboard_markup = ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True, selective=True)
            update.message.reply_text(self.strings["group_repost_reset_initial_prompt"],
                                      reply_markup=keyboard_markup)
            return RepostBot.RESET_CONFIRMATION_STATE
        else:
            update.message.reply_text(self.strings["group_repost_reset_admin_only"])
            return ConversationHandler.END

    def _handle_reset_confirmation(self, update: Update, context: CallbackContext) -> ConversationState:
        response = self._strip_nonalpha_chars(str(update.message.text).lower())
        bot_response = self.strings["group_repost_reset_cancel"]
        if response in ('y', 'yes', 'yeah', 'yep', 'aye', 'yis', 'yas', 'uh huh', 'sure', 'indeed'):
            self.repostitory.reset_group_repost_data(update.message.chat.id)
            bot_response = self.strings["group_repost_data_reset"]
        update.message.reply_text(bot_response, reply_markup=ReplyKeyboardRemove(selective=True))
        return ConversationHandler.END

    def _strip_nonalpha_chars(self, txt: str) -> str:
        return ''.join(filter(lambda l: l.lower() in 'abcdefghijklmnopqrstuvwxyz', txt))

    def _reset_group_repost_data(self, cid: str) -> NoReturn:
        group_data = self.repostitory.get_group_data(cid)
        new_group_data = {"track": group_data["track"],
                          "reposts": {}
                          }
        self.repostitory.save_group_data(cid, new_group_data)

    def _repost_bot_help(self, update: Update, context: CallbackContext) -> NoReturn:
        bot = context.bot
        bot_name = bot.get_me().first_name
        bot.send_message(update.message.chat.id, self.strings["help_command"].format(name=bot_name))

    def _whitelist_command(self, update: Update, context: CallbackContext) -> NoReturn:
        cid = update.message.chat.id
        reply_message = update.message.reply_to_message
        if reply_message is None:
            update.message.reply_text(self.strings["invalid_whitelist_reply"])
        else:
            keys_were_whitelisted = self.repostitory.whitelist_repostable_in_message(update.message.reply_to_message)
            reply_id = reply_message.message_id
            if keys_were_whitelisted == WhitelistAddStatus.ALREADY_EXISTS:
                context.bot.send_message(cid, self.strings["removed_from_whitelist"])
            elif keys_were_whitelisted == WhitelistAddStatus.FAIL:
                update.message.reply_text(self.strings["invalid_whitelist_reply"])
            else:
                update.message.reply_text(self.strings["successful_whitelist_reply"], reply_to_message_id=reply_id)

    def _toggle_tracking(self, update: Update, context: CallbackContext) -> NoReturn:
        group_type = update.message.chat.type
        if group_type == "private":
            update.message.reply_text(self.strings["private_chat_toggle"])
        else:
            cid = update.message.chat.id
            out = list()
            toggle_data = self.repostitory.get_tracking_data(cid)
            for arg in ("url", "picture"):
                if arg in context.args:
                    toggle_data[arg] = not toggle_data[arg]
                    out.append(f"Tracking {arg}s: {toggle_data[arg]}")
            self.repostitory.save_tracking_data(cid, toggle_data)
            update.message.reply_text("\n".join(out))

    def _display_toggle_settings(self, update: Update, context: CallbackContext) -> NoReturn:
        cid = update.message.chat.id
        group_toggles = self.repostitory.get_group_data(cid).get("track")
        out = "\n".join(f"Tracking {k}s: {v}" for k, v in group_toggles.items())
        context.bot.send_message(cid, out)

    def _check_potential_repost(self, update: Update, context: CallbackContext) -> NoReturn:
        message = update.message
        if message.chat.type in ("group", "channel", "supergroup"):
            messages_with_same_hash = self.repostitory.get_repost_message_ids(message)
            if message.forward_from is None and messages_with_same_hash is not None and len(messages_with_same_hash) > 0:
                self._call_out_reposts(update, context, messages_with_same_hash)
        else:
            update.message.reply_text(self.strings["private_chat"])

    def _call_out_reposts(self, update: Update, context: CallbackContext, list_of_reposts: List[RepostSet]):
        bot = context.bot
        cid = update.message.chat.id
        bot.send_chat_action(cid, ChatAction.TYPING)
        for repost_set in list_of_reposts:
            update.message.reply_text(self.strings["repost_alert"])
            prev_msg = ""
            for i, repost_msg in enumerate(repost_set[:-1]):
                bot.send_chat_action(cid, ChatAction.TYPING)
                if i == 0:
                    msg = self.strings["first_repost_callout"]
                else:
                    msg = random.choice(list(filter(lambda response: response != prev_msg,
                                                    self.strings["intermediary_callouts"])))

                prev_msg = msg
                bot.send_message(cid, msg, reply_to_message_id=repost_msg)
            bot.send_chat_action(cid, ChatAction.TYPING)
            name = update.message.from_user.first_name
            bot.send_message(cid, self.strings["final_repost_callout"].format(name=name.upper()))


def ensure_proper_config_structure(data: dict) -> bool:
    top_level = ["repost_data_path", "bot_admin_id", "bot_token", "hash_size", "default_callouts", "strings"]
    defaults = ["url", "picture"]
    strings = ["private_chat", "private_chat_toggle", "help_command", "repost_alert", "first_repost_callout",
               "final_repost_callout", "invalid_whitelist_reply", "removed_from_whitelist",
               "successful_whitelist_reply", "group_repost_reset_initial_prompt", "group_repost_reset_admin_only",
               "group_repost_reset_cancel", "group_repost_data_reset"]
    print("testing config file for all required fields")

    print("testing top-level fields:")
    for field in top_level:
        print(f"\ttesting \"{field}\"...", end="")
        if not data.get(field):
            print("ERROR")
            return False
        else:
            print("found")

    print("\ntesting default callout settings:")
    for default in defaults:
        print(f"\ttesting \"{default}\"...", end="")
        if not data.get("default_callouts").get(default):
            print("ERROR")
            return False
        else:
            print("found")

    print("\ntesting bot strings:")
    for string in strings:
        print(f"\ttesting \"{string}\"...", end="")
        if not data.get("strings").get(string):
            print("ERROR")
            return False
        else:
            print("found")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run an instance of Repost Bot over Telegram")
    # required = parser.add_argument_group('config file argument (required)')
    parser.add_argument('-c', '--config', type=str, help='set path of config file relative to this file', required=True)
    args = parser.parse_args()
    config = args.config
    try:
        with open(config, 'r') as f:
            config_data = yaml.safe_load(f)
        ensure_proper_config_structure(config_data)
        repost_data_path: str = config_data["repost_data_path"]
        bot_admin_id: int = config_data["bot_admin_id"]
        telegram_token: str = config_data["bot_token"]
        default_callouts: Dict[str, bool] = config_data["default_callouts"]
        bot_strings: Dict[str, str] = config_data["strings"]
        hash_size: int = config_data["hash_size"]
    except KeyError as e:
        num_keys = len(e.args)
        print(f"Malformed config file -- could not find key{'s' if num_keys > 1 or num_keys == 0 else ''}: {e}")
    except (FileNotFoundError, TypeError) as e:
        print(f"{e.strerror} -- could not find '{config}'")
    else:
        repost_repository = Repostitory(hash_size, repost_data_path, default_callouts)
        rpb = RepostBot(telegram_token, bot_strings, bot_admin_id, repost_repository)
        rpb.run()
