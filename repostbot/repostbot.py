import logging

from telegram import Chat, Bot
from telegram import KeyboardButton
from telegram import ReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove
from telegram import Update
from telegram.error import Unauthorized, BadRequest
from telegram.ext import CallbackContext, Dispatcher
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

from utils import flood_protection, sum_list_lengths, message_from_anonymous_admin, RepostBotTelegramParams, \
    strip_nonalpha_chars, get_repost_params, flatten_repost_lists_except_original
from .conversation_state import ConversationState
from .repostitory import Repostitory
from .strategies import RepostCalloutStrategy
from .toggles import Toggles
from .whitelist_status import WhitelistAddStatus

logger = logging.getLogger("RepostBot")

NON_PRIVATE_GROUP_FILTER = ~Filters.chat_type.private

CHECK_FOR_REPOST_FILTERS = NON_PRIVATE_GROUP_FILTER & \
                           (Filters.photo | Filters.entity("url")) & \
                           ~(Filters.forwarded & ~Filters.sender_chat.channel)


class RepostBot:

    def __init__(self,
                 token: str,
                 strings: dict[str, str],
                 admin_id: int,
                 repost_callout_strategy: type[RepostCalloutStrategy],
                 flood_protection_seconds: int,
                 repostitory: Repostitory):
        self.token = token
        self.admin_id = admin_id
        self.strings = strings
        self.repostitory = repostitory
        self.repost_callout_strategy = repost_callout_strategy(self.strings)
        self.flood_protection_seconds = flood_protection_seconds

        self.updater: Updater = Updater(self.token)
        self.dp: Dispatcher = self.updater.dispatcher
        self.dp.add_handler(MessageHandler(CHECK_FOR_REPOST_FILTERS, self._check_potential_repost))
        self.dp.add_handler(CommandHandler("toggle", self._set_toggles, filters=NON_PRIVATE_GROUP_FILTER))

        self.dp.add_handler(ConversationHandler(
            entry_points=[CommandHandler("reset", self._reset_prompt_from_command, filters=NON_PRIVATE_GROUP_FILTER)],
            states={
                ConversationState.RESET_CONFIRMATION_STATE: [
                    MessageHandler(Filters.text, self._handle_reset_confirmation)
                ]
            },
            fallbacks=[],
            conversation_timeout=60
        ))

        self.dp.add_handler(CommandHandler("help", self._repost_bot_help, run_async=True))
        self.dp.add_handler(CommandHandler("settings", self._display_toggle_settings, filters=NON_PRIVATE_GROUP_FILTER))
        self.dp.add_handler(CommandHandler("whitelist", self._whitelist_command, filters=NON_PRIVATE_GROUP_FILTER))
        self.dp.add_handler(CommandHandler("stats", self._stats_command, filters=NON_PRIVATE_GROUP_FILTER))
        self.dp.add_handler(CommandHandler("userid", self._userid_reply, filters=~NON_PRIVATE_GROUP_FILTER))

    def run(self) -> None:
        self.updater.start_polling()
        logger.info("Bot is running")
        self.updater.idle()

    @get_repost_params
    def _check_potential_repost(self,
                                update: Update,
                                context: CallbackContext,
                                params: RepostBotTelegramParams) -> None:
        hash_to_message_ids_map = self.repostitory.process_message_entities(params)
        hashes_with_reposts = {
            entity_hash: message_ids
            for entity_hash, message_ids in hash_to_message_ids_map.items()
            if len(message_ids) > 1
        }
        if any(len(messages) > 0 for messages in hashes_with_reposts.values()):
            toggles = self.repostitory.get_toggles_data(params.group_id)
            if toggles.auto_callout:
                self._call_out_reposts(update, context, params, hashes_with_reposts)
            if toggles.auto_delete:
                self._delete_reposts(params.group_id, hashes_with_reposts, context.bot)

    @flood_protection("call_out_reposts")
    def _call_out_reposts(self,
                          update: Update,
                          context: CallbackContext,
                          params: RepostBotTelegramParams,
                          hash_to_message_id_dict: dict[str, list[int]]) -> None:
        self.repost_callout_strategy.callout(context, hash_to_message_id_dict, params)

    def _delete_reposts(self, group_id: int, hashes_with_reposts: dict[str, list[int]], bot: Bot) -> None:
        deleted_messages = self.repostitory.get_deleted_messages(group_id)
        flattened_messages = flatten_repost_lists_except_original(list(hashes_with_reposts.values()))
        newly_deleted_messages = set()
        for message_id in (msg_id for msg_id in flattened_messages if msg_id not in deleted_messages):
            try:
                bot.delete_message(group_id, message_id)
            except (Unauthorized, BadRequest) as e:
                logger.error(e.message)
            else:
                newly_deleted_messages.add(message_id)
        self.repostitory.updated_deleted_messages(group_id, newly_deleted_messages)

    @flood_protection("toggle")
    @get_repost_params
    def _set_toggles(self,
                     update: Update,
                     context: CallbackContext,
                     params: RepostBotTelegramParams) -> None:
        message = params.effective_message
        if message.chat.type == Chat.PRIVATE:
            message.reply_text(self.strings["private_chat_toggle"])
            return
        group_id = message.chat.id
        responses = list()
        toggle_data = self.repostitory.get_toggles_data(group_id)
        for toggle_type, arg in Toggles.get_toggle_args():
            if arg in context.args:
                toggle_data[toggle_type] = not toggle_data[toggle_type]
                toggle_name = Toggles.get_toggle_display_name(toggle_type, self.strings)
                display_value = self.strings["enabled"] if toggle_data[toggle_type] else self.strings["disabled"]
                responses.append(f"{toggle_name}: {display_value}")
        self.repostitory.save_toggles_data(group_id, toggle_data)
        message.reply_text("\n".join(responses))

    @flood_protection("reset")
    @get_repost_params
    def _reset_prompt_from_command(self,
                                   update: Update,
                                   context: CallbackContext,
                                   params: RepostBotTelegramParams) -> int:
        user_id = params.sender_id
        message = params.effective_message
        chat = message.chat
        if (user_id == self.admin_id
                or user_id in (chat_member.user.id for chat_member in chat.get_administrators())
                or message_from_anonymous_admin(message)
        ):
            keyboard_buttons = [
                [KeyboardButton(self.strings["group_reset_yes"]), KeyboardButton(self.strings["group_reset_no"])]
            ]
            keyboard_markup = ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True, selective=True)
            message.reply_text(self.strings["group_repost_reset_initial_prompt"],
                               reply_markup=keyboard_markup,
                               quote=True)
            return ConversationState.RESET_CONFIRMATION_STATE
        else:
            message.reply_text(self.strings["group_repost_reset_admin_only"])
            return ConversationHandler.END

    @get_repost_params
    def _handle_reset_confirmation(self,
                                   update: Update,
                                   context: CallbackContext,
                                   params: RepostBotTelegramParams) -> int:
        response = strip_nonalpha_chars(str(params.effective_message.text))
        bot_response = self.strings["group_repost_reset_cancel"]
        if response in self.strings["group_reset_confirmation_responses"]:
            self.repostitory.reset_group_repost_data(params.group_id)
            bot_response = self.strings["group_repost_data_reset"]
        params.effective_message.reply_text(bot_response, reply_markup=ReplyKeyboardRemove(), quote=True)
        return ConversationHandler.END

    @flood_protection("help")
    @get_repost_params
    def _repost_bot_help(self,
                         update: Update,
                         context: CallbackContext,
                         params: RepostBotTelegramParams) -> None:
        bot_name = context.bot.get_me().first_name
        params.effective_message.reply_text(self.strings["help_command"].format(name=bot_name), quote=True)

    @flood_protection("settings")
    @get_repost_params
    def _display_toggle_settings(self,
                                 update: Update,
                                 context: CallbackContext,
                                 params: RepostBotTelegramParams) -> None:
        group_toggles = self.repostitory.get_toggles_data(params.group_id)
        responses = [self.strings['settings_command_response']]
        for toggle_type, _ in group_toggles.get_toggle_args():
            display_name = Toggles.get_toggle_display_name(toggle_type, self.strings)
            display_value = self.strings['enabled'] if group_toggles[toggle_type] else self.strings['disabled']
            responses.append(
                f"{display_name}: {display_value}"
            )
        params.effective_message.reply_text("\n".join(responses))

    @flood_protection("whitelist")
    @get_repost_params
    def _whitelist_command(self,
                           update: Update,
                           context: CallbackContext,
                           params: RepostBotTelegramParams) -> None:
        message = params.effective_message
        reply_message = message.reply_to_message
        if reply_message is None:
            message.reply_text(self.strings["invalid_whitelist_reply"], quote=True)
            return
        whitelist_command_result = self.repostitory.process_whitelist_command(reply_message, params.group_id)
        response = self.strings["successful_whitelist_reply"]
        if whitelist_command_result == WhitelistAddStatus.ALREADY_EXISTS:
            response = self.strings["removed_from_whitelist"]
        elif whitelist_command_result == WhitelistAddStatus.FAIL:
            response = self.strings["invalid_whitelist_reply"]
        message.reply_text(response, quote=True)

    @flood_protection("stats")
    @get_repost_params
    def _stats_command(self,
                       update: Update,
                       context: CallbackContext,
                       params: RepostBotTelegramParams) -> None:
        group_reposts: dict[str, list[int]] = self.repostitory.get_group_data(params.group_id).reposts
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

    def _userid_reply(self, update: Update, context: CallbackContext) -> None:
        update.effective_message.reply_text(update.effective_user.id)
