import logging

import telegram.ext.filters as filters
from telegram import Chat, Bot
from telegram import KeyboardButton
from telegram import ReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove
from telegram import Update
from telegram.error import Forbidden, BadRequest
from telegram.ext import CallbackContext, Application
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import MessageHandler

from utils import flood_protection, sum_list_lengths, message_from_anonymous_admin, RepostBotTelegramParams, \
    strip_nonalpha_chars, get_repost_params, flatten_repost_lists_except_original
from .conversation_state import ConversationState
from .repostitory import Repostitory
from .strategies import RepostCalloutStrategy
from .toggles import Toggles
from .whitelist_status import WhitelistAddStatus

logger = logging.getLogger("RepostBot")

NON_PRIVATE_GROUP_FILTER = ~filters.ChatType.PRIVATE

CHECK_FOR_REPOST_FILTERS = NON_PRIVATE_GROUP_FILTER & \
                           (filters.PHOTO | filters.Entity("url")) & \
                           ~(filters.FORWARDED & ~filters.SenderChat.CHANNEL)

URL_KEY_LENGTH = 64


async def _userid_reply(update: Update, context: CallbackContext) -> None:
    await update.effective_message.reply_text(str(update.effective_user.id))


class RepostBot:

    def __init__(self,
                 token: str,
                 strings: dict[str, str],
                 admin_id: int,
                 repost_callout_strategy: type[RepostCalloutStrategy],
                 flood_protection_timeout: int,
                 repostitory: Repostitory,
                 group_whitelist: list[int],
                 group_blacklist: list[int]):
        self.token = token
        self.admin_id = admin_id
        self.strings = strings
        self.repostitory = repostitory
        self.repost_callout_strategy = repost_callout_strategy(self.strings)
        self.flood_protection_timeout = flood_protection_timeout
        self.group_whitelist = group_whitelist
        self.group_blacklist = group_blacklist

        self.config_group_filter = (filters.Chat(chat_id=group_whitelist, allow_empty=True) &
                                    ~filters.Chat(chat_id=group_blacklist))

        self.default_group_filter = self.config_group_filter & NON_PRIVATE_GROUP_FILTER

        self.application: Application = Application.builder().token(token).build()

        self.application.add_handlers([
            MessageHandler(callback=self._check_potential_repost,
                           filters=self.config_group_filter & CHECK_FOR_REPOST_FILTERS,
                           block=False),

            CommandHandler(command="toggle",
                           callback=self._set_toggles,
                           filters=self.default_group_filter),

            ConversationHandler(entry_points=[CommandHandler(command="reset",
                                                             callback=self._reset_prompt_from_command,
                                                             filters=self.default_group_filter)],
                                states={
                                    ConversationState.RESET_CONFIRMATION_STATE: [
                                        MessageHandler(filters=self.config_group_filter & filters.TEXT,
                                                       callback=self._handle_reset_confirmation)
                                    ]
                                },
                                fallbacks=[],
                                conversation_timeout=60),

            CommandHandler(command="help",
                           callback=self._repost_bot_help,
                           block=False),

            CommandHandler(command="settings",
                           callback=self._display_toggle_settings,
                           filters=self.default_group_filter),

            CommandHandler(command="whitelist",
                           callback=self._whitelist_command,
                           filters=self.default_group_filter),

            CommandHandler(command="stats",
                           callback=self._stats_command,
                           filters=self.default_group_filter),

            CommandHandler(command="userid",
                           callback=_userid_reply,
                           filters=self.config_group_filter & ~NON_PRIVATE_GROUP_FILTER),
        ])

    def run(self) -> None:
        logger.info("Bot is running")
        self.application.run_polling()

    @get_repost_params
    async def _check_potential_repost(self,
                                      update: Update,
                                      context: CallbackContext,
                                      params: RepostBotTelegramParams = None):
        hash_to_message_ids_map = await self.repostitory.process_message_entities(params)
        hashes_with_reposts = {
            entity_hash: message_ids
            for entity_hash, message_ids in hash_to_message_ids_map.items()
            if len(message_ids) > 1
        }
        if any(len(messages) > 0 for messages in hashes_with_reposts.values()):
            toggles = self.repostitory.get_toggles_data(params.group_id)
            if toggles.auto_callout:
                await self._call_out_reposts(update, context, params, hashes_with_reposts)
            if toggles.auto_delete:
                await self._delete_reposts(params.group_id, hashes_with_reposts, context.bot)

    @flood_protection("call_out_reposts")
    async def _call_out_reposts(self,
                                update: Update,
                                context: CallbackContext,
                                params: RepostBotTelegramParams,
                                hash_to_message_id_dict: dict[str, list[int]]) -> None:
        await self.repost_callout_strategy.callout(context, hash_to_message_id_dict, params)

    async def _delete_reposts(self, group_id: int, hashes_with_reposts: dict[str, list[int]], bot: Bot) -> None:
        deleted_messages: set[int] = self.repostitory.get_deleted_messages(group_id)
        flattened_messages: set[int] = set(flatten_repost_lists_except_original(list(hashes_with_reposts.values())))
        newly_deleted_messages = set()
        for message_id in flattened_messages.difference(deleted_messages):
            try:
                await bot.delete_message(group_id, message_id)
            except (Forbidden, BadRequest) as e:
                logger.error(e.message)
            else:
                newly_deleted_messages.add(message_id)
        self.repostitory.updated_deleted_messages(group_id, newly_deleted_messages)

    @get_repost_params
    @flood_protection("toggle")
    async def _set_toggles(self,
                           update: Update,
                           context: CallbackContext,
                           params: RepostBotTelegramParams = None) -> None:
        message = params.effective_message
        if message.chat.type == Chat.PRIVATE:
            await message.reply_text(self.strings["private_chat_toggle"])
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
        await message.reply_text("\n".join(responses))

    @get_repost_params
    @flood_protection("reset")
    async def _reset_prompt_from_command(self,
                                         update: Update,
                                         context: CallbackContext,
                                         params: RepostBotTelegramParams = None) -> int:
        user_id = params.sender_id
        message = params.effective_message
        chat = message.chat
        if (user_id == self.admin_id
                or user_id in (chat_member.user.id for chat_member in await chat.get_administrators())
                or message_from_anonymous_admin(user_id)
        ):
            keyboard_buttons = [
                [KeyboardButton(self.strings["group_reset_yes"]), KeyboardButton(self.strings["group_reset_no"])]
            ]
            keyboard_markup = ReplyKeyboardMarkup(keyboard_buttons, one_time_keyboard=True, selective=True)
            await message.reply_text(self.strings["group_repost_reset_initial_prompt"],
                                     reply_markup=keyboard_markup,
                                     quote=True)
            return ConversationState.RESET_CONFIRMATION_STATE
        else:
            await message.reply_text(self.strings["group_repost_reset_admin_only"])
            return ConversationHandler.END

    @get_repost_params
    async def _handle_reset_confirmation(self,
                                         update: Update,
                                         context: CallbackContext,
                                         params: RepostBotTelegramParams = None) -> int:
        response = strip_nonalpha_chars(str(params.effective_message.text))
        bot_response = self.strings["group_repost_reset_cancel"]
        if response in self.strings["group_reset_confirmation_responses"]:
            self.repostitory.reset_group_repost_data(params.group_id)
            bot_response = self.strings["group_repost_data_reset"]
        await params.effective_message.reply_text(bot_response, reply_markup=ReplyKeyboardRemove(), quote=True)
        return ConversationHandler.END

    @get_repost_params
    @flood_protection("help")
    async def _repost_bot_help(self,
                               update: Update,
                               context: CallbackContext,
                               params: RepostBotTelegramParams = None) -> None:
        bot_name = context.bot.first_name
        group_id = params.group_id
        group_filter_response = None
        if (len(self.group_whitelist) > 0) and group_id not in self.group_whitelist:
            group_filter_response = self.strings["not_in_whitelist_response"]
        elif group_id in self.group_blacklist:
            group_filter_response = self.strings["blacklisted_response"]

        if group_filter_response:
            await params.effective_message.reply_text(group_filter_response)
        else:
            await params.effective_message.reply_text(self.strings["help_command"].format(name=bot_name), quote=True)

    @get_repost_params
    @flood_protection("settings")
    async def _display_toggle_settings(self,
                                       update: Update,
                                       context: CallbackContext,
                                       params: RepostBotTelegramParams = None) -> None:
        group_toggles = self.repostitory.get_toggles_data(params.group_id)
        responses = [self.strings['settings_command_response']]
        for toggle_type, _ in group_toggles.get_toggle_args():
            display_name = Toggles.get_toggle_display_name(toggle_type, self.strings)
            display_value = self.strings['enabled'] if group_toggles[toggle_type] else self.strings['disabled']
            responses.append(
                f"{display_name}: {display_value}"
            )
        await params.effective_message.reply_text("\n".join(responses))

    @get_repost_params
    @flood_protection("whitelist")
    async def _whitelist_command(self,
                                 update: Update,
                                 context: CallbackContext,
                                 params: RepostBotTelegramParams = None) -> None:
        message = params.effective_message
        reply_message = message.reply_to_message
        if reply_message is None:
            await message.reply_text(self.strings["invalid_whitelist_reply"], quote=True)
            return

        match await self.repostitory.process_whitelist_command(reply_message, params.group_id):
            case WhitelistAddStatus.SUCCESS:
                response = self.strings["successful_whitelist_reply"]
            case WhitelistAddStatus.ALREADY_EXISTS:
                response = self.strings["removed_from_whitelist_reply"]
            case WhitelistAddStatus.ADDED_AND_REMOVED:
                response = self.strings["added_and_removed_from_whitelist_reply"]
            case _:
                response = self.strings["invalid_whitelist_reply"]

        await message.reply_text(response, quote=True)

    @get_repost_params
    @flood_protection("stats")
    async def _stats_command(self,
                             update: Update,
                             context: CallbackContext,
                             params: RepostBotTelegramParams = None) -> None:
        group_reposts: dict[str, list[int]] = self.repostitory.get_group_reposts(params.group_id)
        url_reposts = dict()
        image_reposts = dict()
        for key, repost_list in group_reposts.items():
            only_reposts = repost_list[1:]
            (url_reposts if len(key) == URL_KEY_LENGTH else image_reposts).update({key: only_reposts})
        num_unique_images = len(image_reposts.keys())
        num_image_reposts = sum_list_lengths(image_reposts.values())
        num_unique_urls = len(url_reposts.keys())
        num_url_reposts = sum_list_lengths(url_reposts.values())
        response = self.strings["stats_command_reply"].format(num_unique_images=num_unique_images,
                                                              num_image_reposts=num_image_reposts,
                                                              num_unique_urls=num_unique_urls,
                                                              num_url_reposts=num_url_reposts)
        await params.effective_message.reply_text(response, quote=True)
