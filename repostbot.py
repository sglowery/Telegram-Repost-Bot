import logging
from typing import Dict, Type
from typing import List
from typing import NoReturn

from telegram import ChatAction
from telegram import KeyboardButton
from telegram import ReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

from conversation_state import ConversationState
from repostitory import Repostitory
from strategies import RepostCalloutStrategy
from whitelist_status import WhitelistAddStatus

logger = logging.getLogger(__name__)


class RepostBot:

    def __init__(self, token: str, strings: Dict[str, str], admin_id: int, repostitory: Repostitory,
                 repost_callout_strategy: Type[RepostCalloutStrategy], auto_call_out: bool):
        self.token = token
        self.admin_id = admin_id
        self.strings = strings
        self.repostitory = repostitory
        self.repost_callout_strategy = repost_callout_strategy(self.strings)
        self.auto_call_out = auto_call_out

        reset_conversation_states = {
            ConversationState.RESET_CONFIRMATION_STATE: [MessageHandler(Filters.text, self._handle_reset_confirmation)]
        }

        self.updater = Updater(self.token)
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

    def _check_potential_repost(self, update: Update, context: CallbackContext) -> NoReturn:
        message = update.message
        if message.chat.type in ("group", "channel", "supergroup"):
            hash_to_message_id_map = self.repostitory.process_message_entities(message)
            hashes_with_reposts = {entity_hash: message_ids for entity_hash, message_ids in hash_to_message_id_map.items() if len(message_ids) > 1}
            if message.forward_from is None and len(hashes_with_reposts) > 0 and self.auto_call_out:
                self._call_out_reposts(update, context, hashes_with_reposts)
        else:
            update.message.reply_text(self.strings["private_chat"])

    def _toggle_tracking(self, update: Update, context: CallbackContext) -> NoReturn:
        group_type = update.message.chat.type
        if group_type == "private":
            update.message.reply_text(self.strings["private_chat_toggle"])
        else:
            group_id = update.message.chat.id
            responses = list()
            toggle_data = self.repostitory.get_tracking_data(group_id)
            for arg in ("url", "picture"):
                if arg in context.args:
                    toggle_data[arg] = not toggle_data[arg]
                    responses.append(f"Tracking {arg}s: {toggle_data[arg]}")
            self.repostitory.save_tracking_data(group_id, toggle_data)
            update.message.reply_text("\n".join(responses))

    def _reset_prompt_from_command(self, update: Update, context: CallbackContext) -> ConversationState:
        user = update.message.from_user
        chat = update.message.chat
        if user.id == self.admin_id or user.id in (chat_member.user.id for chat_member in chat.get_administrators()):
            keyboard_buttons = [[KeyboardButton("Yes"), KeyboardButton("No")]]
            keyboard_markup = ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True, selective=True)
            update.message.reply_text(self.strings["group_repost_reset_initial_prompt"],
                                      reply_markup=keyboard_markup)
            return ConversationState.RESET_CONFIRMATION_STATE
        else:
            update.message.reply_text(self.strings["group_repost_reset_admin_only"])
            return ConversationHandler.END

    def _handle_reset_confirmation(self, update: Update, context: CallbackContext) -> ConversationState:
        response = self._strip_nonalpha_chars(str(update.message.text).lower())
        bot_response = self.strings["group_repost_reset_cancel"]
        if response in ('y', 'ye', 'yes', 'yeah', 'yep', 'aye', 'yis', 'yas', 'uh huh', 'sure', 'indeed'):
            self.repostitory.reset_group_repost_data(update.message.chat.id)
            bot_response = self.strings["group_repost_data_reset"]
        update.message.reply_text(bot_response, reply_markup=ReplyKeyboardRemove(selective=True))
        return ConversationHandler.END

    def _repost_bot_help(self, update: Update, context: CallbackContext) -> NoReturn:
        bot = context.bot
        bot_name = bot.get_me().first_name
        bot.send_message(update.message.chat.id, self.strings["help_command"].format(name=bot_name))

    def _display_toggle_settings(self, update: Update, context: CallbackContext) -> NoReturn:
        group_id = update.message.chat.id
        group_toggles = self.repostitory.get_group_data(group_id).get("track")
        response = "\n".join(f"Tracking {k}s: {v}" for k, v in group_toggles.items())
        context.bot.send_message(group_id, response)

    def _whitelist_command(self, update: Update, context: CallbackContext) -> NoReturn:
        group_id = update.message.chat.id
        reply_message = update.message.reply_to_message
        if reply_message is None:
            update.message.reply_text(self.strings["invalid_whitelist_reply"])
        else:
            whitelist_command_result = self.repostitory.whitelist_repostable_in_message(update.message.reply_to_message)
            reply_id = reply_message.message_id
            if whitelist_command_result == WhitelistAddStatus.ALREADY_EXISTS:
                context.bot.send_message(group_id, self.strings["removed_from_whitelist"])
            elif whitelist_command_result == WhitelistAddStatus.FAIL:
                update.message.reply_text(self.strings["invalid_whitelist_reply"])
            else:
                update.message.reply_text(self.strings["successful_whitelist_reply"], reply_to_message_id=reply_id)

    def _call_out_reposts(self,
                          update: Update,
                          context: CallbackContext,
                          hash_to_message_id_dict: Dict[str, List[int]]):
        bot = context.bot
        cid = update.message.chat.id
        bot.send_chat_action(cid, ChatAction.TYPING)
        self.repost_callout_strategy.callout(update, context, hash_to_message_id_dict)

    def _strip_nonalpha_chars(self, txt: str) -> str:
        text_lower = txt.lower()
        return ''.join(letter for letter in text_lower if letter in 'abcdefghijklmnopqrstuvwxyz')
