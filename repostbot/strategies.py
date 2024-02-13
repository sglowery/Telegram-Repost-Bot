import logging
import random
from abc import ABC, abstractmethod

from telegram import Chat
from telegram.constants import ChatAction
from telegram.ext import CallbackContext

from utils import is_post_from_channel, RepostBotTelegramParams

logger = logging.getLogger("Strategies")


def _format_response_with_name(response: str, name: str, **kwargs) -> str:
    return response.format(name=name, **kwargs)


def _get_name_from_params(params: RepostBotTelegramParams) -> str:
    user_id = params.sender_id
    forward_from_chat = params.effective_message.forward_from_chat if params.effective_message is not None else None
    if is_post_from_channel(user_id) or (forward_from_chat is not None and forward_from_chat.type == Chat.CHANNEL):
        return forward_from_chat.title
    else:
        return params.sender_name


class RepostCalloutStrategy(ABC):
    def __init__(self, strings: dict[str, str | list[str]]):
        self.strings = strings

    @abstractmethod
    async def callout(self,
                      context: CallbackContext,
                      hash_to_message_id_dict: dict[str, list[int]],
                      params: RepostBotTelegramParams) -> None:
        logger.info("Calling out repost")

    @staticmethod
    @abstractmethod
    def get_required_strings() -> list[str]:
        pass


class _VerboseCalloutStyleStrategy(RepostCalloutStrategy):

    def __init__(self, strings: dict[str, str | list[str]]):
        super().__init__(strings)

    @staticmethod
    def get_required_strings() -> list[str]:
        return ["repost_alert", "first_repost_callout", "final_repost_callout", "intermediary_callouts"]

    async def callout(self,
                      context: CallbackContext,
                      hash_to_message_id_dict: dict[str, list[int]],
                      params: RepostBotTelegramParams):
        await super().callout(context, hash_to_message_id_dict, params)
        message = params.effective_message
        cid = params.group_id
        bot = context.bot
        name = _get_name_from_params(params)
        for message_ids in hash_to_message_id_dict.values():
            await bot.send_chat_action(cid, ChatAction.TYPING)
            await message.reply_text(self.strings["repost_alert"])
            prev_msg = ""
            for i, repost_msg in enumerate(message_ids[:-1]):
                await bot.send_chat_action(cid, ChatAction.TYPING)
                msg = self._get_message(i, prev_msg)
                prev_msg = msg
                await message.reply_text(_format_response_with_name(msg, name))
            await bot.send_chat_action(cid, ChatAction.TYPING)
            await message.reply_text(_format_response_with_name(self.strings["final_repost_callout"], name))

    def _get_message(self, message_num: int, prev_msg: str) -> str:
        if message_num == 0:
            return self.strings["first_repost_callout"]
        return self._get_random_intermediary_message(prev_msg)

    def _get_random_intermediary_message(self, prev_msg: str) -> str:
        return random.choice([response for response in self.strings["intermediary_callouts"] if response != prev_msg])


class _SingularCalloutStyleStrategy(RepostCalloutStrategy):

    def __init__(self, strings: dict[str, str | list[str]]):
        super().__init__(strings)

    @staticmethod
    def get_required_strings() -> list[str]:
        return ["single_callout_one_repost_options", "single_callout_x_num_reposts_options"]

    async def callout(self,
                      context: CallbackContext,
                      hash_to_message_id_dict: dict[str, list[int]],
                      params: RepostBotTelegramParams):
        await super().callout(context, hash_to_message_id_dict, params)
        await context.bot.send_chat_action(params.group_id, ChatAction.TYPING)
        num_reposts = sum(len(message_ids) - 1 for message_ids in hash_to_message_id_dict.values())
        name = _get_name_from_params(params)
        key = "single_callout_one_repost_options" if num_reposts == 1 else "single_callout_x_num_reposts_options"
        response_with_num_and_name = _format_response_with_name(random.choice(self.strings[key]), name, num=num_reposts)
        await params.effective_message.reply_text(response_with_num_and_name, quote=True)


_STRATEGIES: dict[str, type[RepostCalloutStrategy]] = {
    "verbose": _VerboseCalloutStyleStrategy,
    "singular": _SingularCalloutStyleStrategy,
}
DEFAULT_STRATEGY = "singular"


def get_default_strategy() -> type[RepostCalloutStrategy]:
    return _STRATEGIES[DEFAULT_STRATEGY]


def get_callout_strategy(strategy: str) -> type[RepostCalloutStrategy]:
    try:
        return _STRATEGIES[strategy.lower().strip()]
    except KeyError:
        logger.error(f"Cannot find strategy for {strategy}, using default {DEFAULT_STRATEGY}")
    return _STRATEGIES[DEFAULT_STRATEGY]


def get_all_callout_strategies() -> list[type[RepostCalloutStrategy]]:
    return list(_STRATEGIES.values())
