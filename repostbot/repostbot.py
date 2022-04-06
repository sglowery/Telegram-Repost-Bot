import logging
from typing import Dict, Type
from typing import List

from telegram import Chat
from telegram import KeyboardButton
from telegram import ReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove
from telegram import Update
from telegram.ext import CallbackContext, Dispatcher
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

from util.utils import flood_protection, sum_list_lengths, message_from_anonymous_admin, RepostBotTelegramParams, \
    strip_nonalpha_chars, get_repost_params
from .conversation_state import ConversationState
from .repostitory import Repostitory
from .strategies import RepostCalloutStrategy
from .whitelist_status import WhitelistAddStatus

logger = logging.getLogger("RepostBot")

NON_PRIVATE_GROUP_FILTERS = Filters.chat_type.group | Filters.chat_type.supergroup | Filters.chat_type.channel


class RepostBot:

    def __init__(self,
                 token: str,
                 strings: Dict[str, str],
                 admin_id: int,
                 repost_callout_strategy: Type[RepostCalloutStrategy],
                 auto_call_out: bool,
                 flood_protection_seconds: int,
                 hash_size: int,
                 repost_data_path: str,
                 default_callouts: Dict[str, bool]):
        self.token = token
        self.admin_id = admin_id
        self.strings = strings
        self.repostitory = Repostitory(hash_size, repost_data_path, default_callouts)
        self.repost_callout_strategy = repost_callout_strategy(self.strings)
        self.auto_call_out = auto_call_out
        self.flood_protection_seconds = flood_protection_seconds

        self.updater: Updater = Updater(self.token)
        self.dp: Dispatcher = self.updater.dispatcher
        self.dp.add_handler(MessageHandler(NON_PRIVATE_GROUP_FILTERS &
                                           (Filters.photo | Filters.entity("url")) &
                                           ~(Filters.forwarded & ~Filters.sender_chat.channel),
                                           self._check_potential_repost))
        self.dp.add_handler(CommandHandler("toggle", self._toggle_tracking, filters=NON_PRIVATE_GROUP_FILTERS))

        self.dp.add_handler(ConversationHandler(
            entry_points=[CommandHandler("reset", self._reset_prompt_from_command, filters=NON_PRIVATE_GROUP_FILTERS)],
            states={ConversationState.RESET_CONFIRMATION_STATE: [MessageHandler(Filters.text, self._handle_reset_confirmation)]},
            fallbacks=[],
            conversation_timeout=60
        ))

        self.dp.add_handler(CommandHandler("help", self._repost_bot_help, run_async=True))
        self.dp.add_handler(CommandHandler("settings", self._display_toggle_settings, filters=NON_PRIVATE_GROUP_FILTERS))
        self.dp.add_handler(CommandHandler("whitelist", self._whitelist_command, filters=NON_PRIVATE_GROUP_FILTERS))
        self.dp.add_handler(CommandHandler("stats", self._stats_command, filters=NON_PRIVATE_GROUP_FILTERS))
        self.dp.add_handler(CommandHandler("userid", self._userid_reply, filters=~NON_PRIVATE_GROUP_FILTERS))

    def run(self) -> None:
        self.updater.start_polling()
        logger.info("Bot is running")
        self.updater.idle()

    @get_repost_params
    def _check_potential_repost(self, update: Update, context: CallbackContext, params: RepostBotTelegramParams) -> None:
        hash_to_message_id_map = self.repostitory.process_message_entities(params)
        hashes_with_reposts = {
            entity_hash: message_ids
            for entity_hash, message_ids in hash_to_message_id_map.items()
            if len(message_ids) > 1
        }
        if any(len(reposts) > 0 for reposts in hashes_with_reposts.values()) and self.auto_call_out:
            self._call_out_reposts(update, context, params, hashes_with_reposts)

    @flood_protection("toggle")
    @get_repost_params
    def _toggle_tracking(self, update: Update, context: CallbackContext, params: RepostBotTelegramParams) -> None:
        message = params.effective_message
        group_type = message.chat.type
        if group_type == Chat.PRIVATE:
            message.reply_text(self.strings["private_chat_toggle"])
        else:
            group_id = message.chat.id
            responses = list()
            toggle_data = self.repostitory.get_tracking_data(group_id)
            for arg in ("url", "picture"):
                if arg in context.args:
                    toggle_data[arg] = not toggle_data[arg]
                    responses.append(f"Tracking {arg}s: {toggle_data[arg]}")
            self.repostitory.save_tracking_data(group_id, toggle_data)
            message.reply_text("\n".join(responses))

    @flood_protection("reset")
    @get_repost_params
    def _reset_prompt_from_command(self, update: Update, context: CallbackContext, params: RepostBotTelegramParams) -> ConversationState:
        user_id = params.sender_id
        message = params.effective_message
        chat = message.chat
        if user_id == self.admin_id or \
                user_id in (chat_member.user.id for chat_member in chat.get_administrators()) or \
                message_from_anonymous_admin(message):
            keyboard_buttons = [[KeyboardButton("Yes"), KeyboardButton("No")]]
            keyboard_markup = ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True, selective=True)
            message.reply_text(self.strings["group_repost_reset_initial_prompt"],
                               reply_markup=keyboard_markup,
                               quote=True)
            return ConversationState.RESET_CONFIRMATION_STATE
        else:
            message.reply_text(self.strings["group_repost_reset_admin_only"])
            return ConversationHandler.END

    @get_repost_params
    def _handle_reset_confirmation(self, update: Update, context: CallbackContext, params: RepostBotTelegramParams) -> ConversationState:
        response = strip_nonalpha_chars(str(params.effective_message.text))
        bot_response = self.strings["group_repost_reset_cancel"]
        if response in ('y', 'ye', 'yes', 'yeah', 'yep', 'aye', 'yis', 'yas', 'uhhuh', 'sure', 'indeed'):
            self.repostitory.reset_group_repost_data(params.group_id)
            bot_response = self.strings["group_repost_data_reset"]
        params.effective_message.reply_text(bot_response, reply_markup=ReplyKeyboardRemove(), quote=True)
        return ConversationHandler.END

    @flood_protection("help")
    @get_repost_params
    def _repost_bot_help(self, update: Update, context: CallbackContext, params: RepostBotTelegramParams) -> None:
        bot_name = context.bot.get_me().first_name
        params.effective_message.reply_text(self.strings["help_command"].format(name=bot_name), quote=True)

    @flood_protection("settings")
    @get_repost_params
    def _display_toggle_settings(self, update: Update, context: CallbackContext, params: RepostBotTelegramParams) -> None:
        group_id = params.group_id
        group_toggles = self.repostitory.get_group_data(group_id).get("track")
        response = "\n".join(f"Tracking {k}s: {v}" for k, v in group_toggles.items())
        params.effective_message.reply_text(response)

    @flood_protection("whitelist")
    @get_repost_params
    def _whitelist_command(self, update: Update, context: CallbackContext, params: RepostBotTelegramParams) -> None:
        message = params.effective_message
        reply_message = message.reply_to_message
        if reply_message is None:
            message.reply_text(self.strings["invalid_whitelist_reply"], quote=True)
        else:
            whitelist_command_result = self.repostitory.process_whitelist_command_on_message(reply_message, params.group_id)
            if whitelist_command_result == WhitelistAddStatus.ALREADY_EXISTS:
                message.reply_text(self.strings["removed_from_whitelist"], quote=True)
            elif whitelist_command_result == WhitelistAddStatus.FAIL:
                message.reply_text(self.strings["invalid_whitelist_reply"], quote=True)
            else:
                message.reply_text(self.strings["successful_whitelist_reply"], quote=True)

    @flood_protection("stats")
    @get_repost_params
    def _stats_command(self, update: Update, context: CallbackContext, params: RepostBotTelegramParams) -> None:
        group_reposts: Dict[str, List[int]] = self.repostitory.get_group_data(params.group_id).get('reposts')
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
        params.effective_message.reply_text(response, quote=True)

    @flood_protection("call_out_reposts")
    def _call_out_reposts(self,
                          update: Update,
                          context: CallbackContext,
                          params: RepostBotTelegramParams,
                          hash_to_message_id_dict: Dict[str, List[int]]) -> None:
        self.repost_callout_strategy.callout(context, hash_to_message_id_dict, params)

    def _userid_reply(self, update: Update, context: CallbackContext) -> None:
        update.effective_message.reply_text(update.effective_user.id)
