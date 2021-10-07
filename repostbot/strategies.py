import logging
import random
from abc import ABC, abstractmethod
from typing import List, NoReturn, Dict, Type

from telegram import Update, ChatAction, Chat
from telegram.ext import CallbackContext

from util.utils import is_anonymous_admin, is_post_from_channel

logger = logging.getLogger("Strategies")


def _format_response_with_name(response: str, name: str, **kwargs) -> str:
    return response.format(name=name, **kwargs)


def _get_name_to_use(update: Update) -> str:
    user = update.effective_user
    forward_from_chat = update.message.forward_from_chat
    if is_post_from_channel(user) and forward_from_chat and forward_from_chat.type == Chat.CHANNEL:
        return forward_from_chat.title
    elif is_anonymous_admin(user):
        return "Anonymous Admin"
    else:
        return update.message.from_user.first_name


class RepostCalloutStrategy(ABC):
    def __init__(self, strings: Dict[str, str or List[str]]):
        self.strings = strings

    @abstractmethod
    def callout(self,
                update: Update,
                context: CallbackContext,
                hash_to_message_id_dict: Dict[str, List[int]]) -> NoReturn:
        logger.info("Calling out repost")

    @staticmethod
    @abstractmethod
    def get_required_strings() -> List[str]:
        pass


class _CallOutAllIndividualRepostsStrategy(RepostCalloutStrategy):

    def __init__(self, strings: Dict[str, str or List[str]]):
        super().__init__(strings)

    @staticmethod
    def get_required_strings() -> List[str]:
        return ["repost_alert", "first_repost_callout", "final_repost_callout", "intermediary_callouts"]

    def callout(self, update: Update, context: CallbackContext, hash_to_message_id_dict: Dict[str, List[int]]):
        super().callout(update, context, hash_to_message_id_dict)
        message = update.message
        cid = message.chat.id
        bot = context.bot
        name = _get_name_to_use(update)
        for message_ids in hash_to_message_id_dict.values():
            message.reply_text(self.strings["repost_alert"])
            prev_msg = ""
            for i, repost_msg in enumerate(message_ids[:-1]):
                bot.send_chat_action(cid, ChatAction.TYPING)
                msg = self._get_random_intermediary_message(prev_msg)
                if i == 0:
                    msg = self.strings["first_repost_callout"]
                prev_msg = msg
                bot.send_message(cid, _format_response_with_name(msg, name), reply_to_message_id=repost_msg)
            bot.send_chat_action(cid, ChatAction.TYPING)
            message.reply_text(_format_response_with_name(self.strings["final_repost_callout"], name))

    def _get_random_intermediary_message(self, prev_msg: str):
        return random.choice([response for response in self.strings["intermediary_callouts"] if response != prev_msg])


class _CallOutNumberOfRepostsStrategy(RepostCalloutStrategy):

    def __init__(self, strings: Dict[str, str or List[str]]):
        super().__init__(strings)

    @staticmethod
    def get_required_strings() -> List[str]:
        return ["single_callout_one_repost_options", "single_callout_x_num_reposts_options"]

    def callout(self, update: Update, context: CallbackContext, hash_to_message_id_dict: Dict[str, List[int]]):
        super().callout(update, context, hash_to_message_id_dict)
        context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        num_reposts = sum(len(message_ids) - 1 for message_ids in hash_to_message_id_dict.values())
        name = _get_name_to_use(update)
        key = "single_callout_one_repost_options" if num_reposts == 1 else "single_callout_x_num_reposts_options"
        response_with_num_and_name = _format_response_with_name(random.choice(self.strings[key]), name, num=num_reposts)
        update.message.reply_text(response_with_num_and_name, quote=True)


STRATEGIES: Dict[str, Type[RepostCalloutStrategy]] = {
    "verbose": _CallOutAllIndividualRepostsStrategy,
    "singular": _CallOutNumberOfRepostsStrategy,
}
DEFAULT_STRATEGY = "singular"


def get_strategy(strategy: str) -> Type[RepostCalloutStrategy]:
    try:
        return STRATEGIES[strategy.lower().strip()]
    except KeyError:
        logger.error(f"Cannot find strategy for {strategy}")
