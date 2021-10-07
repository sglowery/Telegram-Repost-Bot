import logging
from typing import Dict, Type
from typing import List

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

from repostbot.conversation_state import ConversationState
from repostbot.repostitory import Repostitory
from repostbot.strategies import RepostCalloutStrategy
from util.utils import flood_protection, sum_list_lengths, is_anonymous_admin
from repostbot.whitelist_status import WhitelistAddStatus

logger = logging.getLogger("RepostBot")

NON_PRIVATE_GROUP_FILTERS = Filters.chat_type.group | Filters.chat_type.supergroup


class RepostBot:

    def __init__(self,
                 token: str,
                 strings: Dict[str, str],
                 admin_id: int,
                 repostitory: Repostitory,
                 repost_callout_strategy: Type[RepostCalloutStrategy],
                 auto_call_out: bool,
                 flood_protection_seconds: int):
        self.token = token
        self.admin_id = admin_id
        self.strings = strings
        self.repostitory = repostitory
        self.repost_callout_strategy = repost_callout_strategy(self.strings)
        self.auto_call_out = auto_call_out
        self.flood_protection_seconds = flood_protection_seconds

        reset_conversation_states = {
            ConversationState.RESET_CONFIRMATION_STATE: [MessageHandler(Filters.text, self._handle_reset_confirmation)]
        }

        self.updater = Updater(self.token)
        self.dp = self.updater.dispatcher
        self.dp.add_handler(MessageHandler(NON_PRIVATE_GROUP_FILTERS & (Filters.photo | Filters.entity("url")),
                                           self._check_potential_repost))
        self.dp.add_handler(CommandHandler("toggle", self._toggle_tracking, filters=NON_PRIVATE_GROUP_FILTERS))
        self.dp.add_handler(ConversationHandler(
            [CommandHandler("reset", self._reset_prompt_from_command, filters=NON_PRIVATE_GROUP_FILTERS)],
            states=reset_conversation_states,
            fallbacks=[]))
        self.dp.add_handler(CommandHandler("help", self._repost_bot_help))
        self.dp.add_handler(
            CommandHandler("settings", self._display_toggle_settings, filters=NON_PRIVATE_GROUP_FILTERS))
        self.dp.add_handler(CommandHandler("whitelist", self._whitelist_command, filters=NON_PRIVATE_GROUP_FILTERS))
        self.dp.add_handler(CommandHandler("stats", self._stats_command, filters=NON_PRIVATE_GROUP_FILTERS))

    def run(self) -> None:
        self.updater.start_polling()
        logger.info("bot is running")
        self.updater.idle()

    def _check_potential_repost(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        hash_to_message_id_map = self.repostitory.process_message_entities(message)
        hashes_with_reposts = {
            entity_hash: message_ids
            for entity_hash, message_ids in hash_to_message_id_map.items()
            if len(message_ids) > 1
        }
        if message.forward_from is None and \
                any(len(reposts) > 0 for reposts in hashes_with_reposts.values()) and \
                self.auto_call_out:
            self._call_out_reposts(update, context, hashes_with_reposts)

    @flood_protection("toggle")
    def _toggle_tracking(self, update: Update, context: CallbackContext) -> None:
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

    @flood_protection("reset")
    def _reset_prompt_from_command(self, update: Update, context: CallbackContext) -> ConversationState:
        user = update.message.from_user
        chat = update.message.chat
        if user.id == self.admin_id or \
                user.id in (chat_member.user.id for chat_member in chat.get_administrators()) or \
                is_anonymous_admin(user):
            keyboard_buttons = [[KeyboardButton("Yes"), KeyboardButton("No")]]
            keyboard_markup = ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True, selective=True)
            update.message.reply_text(self.strings["group_repost_reset_initial_prompt"],
                                      reply_markup=keyboard_markup,
                                      quote=True)
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
        update.message.reply_text(bot_response, reply_markup=ReplyKeyboardRemove(), quote=True)
        return ConversationHandler.END

    @flood_protection("help")
    def _repost_bot_help(self, update: Update, context: CallbackContext) -> None:
        bot = context.bot
        bot_name = bot.get_me().first_name
        bot.send_message(update.message.chat.id, self.strings["help_command"].format(name=bot_name))

    @flood_protection("settings")
    def _display_toggle_settings(self, update: Update, context: CallbackContext) -> None:
        group_id = update.message.chat.id
        group_toggles = self.repostitory.get_group_data(group_id).get("track")
        response = "\n".join(f"Tracking {k}s: {v}" for k, v in group_toggles.items())
        context.bot.send_message(group_id, response)

    @flood_protection("whitelist")
    def _whitelist_command(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        reply_message = message.reply_to_message
        if reply_message is None:
            message.reply_text(self.strings["invalid_whitelist_reply"], quote=True)
        else:
            whitelist_command_result = self.repostitory.process_whitelist_command_on_message(reply_message)
            if whitelist_command_result == WhitelistAddStatus.ALREADY_EXISTS:
                message.reply_text(self.strings["removed_from_whitelist"], quote=True)
            elif whitelist_command_result == WhitelistAddStatus.FAIL:
                message.reply_text(self.strings["invalid_whitelist_reply"], quote=True)
            else:
                message.reply_text(self.strings["successful_whitelist_reply"], quote=True)

    @flood_protection("stats")
    def _stats_command(self, update: Update, context: CallbackContext) -> None:
        group_reposts: Dict[str, List[int]] = self.repostitory.get_group_data(update.message.chat.id).get('reposts')
        url_reposts = dict()
        image_reposts = dict()
        for key, repost_list in group_reposts.items():
            only_reposts = repost_list[1:]
            (url_reposts if len(key) == 64 else image_reposts).update({key: only_reposts})
        num_unique_images = len(image_reposts.keys())
        num_image_reposts = sum_list_lengths(image_reposts.values())
        num_unique_urls = len(url_reposts.keys())
        num_url_reposts = sum_list_lengths(url_reposts.values())
        response = self.strings["stats_command_reply"].format(num_unique_images=num_unique_images,
                                                              num_image_reposts=num_image_reposts,
                                                              num_unique_urls=num_unique_urls,
                                                              num_url_reposts=num_url_reposts)
        update.message.reply_text(response, quote=True)

    @flood_protection("call_out_reposts")
    def _call_out_reposts(self,
                          update: Update,
                          context: CallbackContext,
                          hash_to_message_id_dict: Dict[str, List[int]]) -> None:
        bot = context.bot
        cid = update.message.chat.id
        bot.send_chat_action(cid, ChatAction.TYPING)
        self.repost_callout_strategy.callout(update, context, hash_to_message_id_dict)

    def _strip_nonalpha_chars(self, txt: str) -> str:
        text_lower = txt.lower()
        return ''.join(letter for letter in text_lower if letter in 'abcdefghijklmnopqrstuvwxyz')
