import asyncio
import itertools
import logging
import string
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import ValuesView

import telegram.constants
from telegram import Update, Message
from telegram.ext import CallbackContext

logger = logging.getLogger("Flood Protection")

_flood_track: dict[int, dict[str, datetime]] = dict()

_lock = asyncio.Lock()


@dataclass(frozen=True)
class RepostBotTelegramParams:
    group_id: int
    sender_id: int
    sender_name: str
    effective_message: Message


def flood_protection(command_key: str):
    def _inner(func):
        @wraps(func)
        async def _wrapped(repostbot_instance,
                           update: Update,
                           context: CallbackContext,
                           *args,
                           **kwargs):
            logger.info(f"Command called: {command_key}")
            effective_user = update.effective_user if update.effective_user is not None else update.effective_chat
            effective_user_id = effective_user.id
            async with _lock:
                _init_tracking_for_user(effective_user_id)
                threshold = repostbot_instance.flood_protection_timeout
                last_called = _flood_track.get(effective_user_id).get(command_key)
                if last_called is None or (datetime.now() - last_called).total_seconds() > threshold:
                    _clean_up_tracking(threshold)
                    _flood_track.get(effective_user_id).update({command_key: datetime.now()})
                    return await func(repostbot_instance, update, context, *args, **kwargs)
                else:
                    logger.info(f"Anti-flood protection on key {command_key}")

        return _wrapped

    return _inner


def _init_tracking_for_user(user_id: int) -> None:
    if _flood_track.get(user_id) is None:
        _flood_track.update({user_id: dict()})


def _clean_up_tracking(threshold: int):
    now = datetime.now()
    updated_flood_track = {
        user_id: {
            command_key: last_command_called
            for command_key, last_command_called in _flood_track.get(user_id).items()
            if (now - last_command_called).total_seconds() > threshold
        }
        for user_id in _flood_track.keys()
    }
    _flood_track.clear()
    _flood_track.update(updated_flood_track)


def sum_list_lengths(lists: ValuesView) -> int:
    return sum(len(_list) for _list in lists)


def message_from_anonymous_admin(user_id: int) -> bool:
    return user_id == telegram.constants.ChatID.ANONYMOUS_ADMIN


def is_post_from_channel(user_id: int | None) -> bool:
    return user_id == telegram.constants.ChatID.FAKE_CHANNEL


def strip_nonalpha_chars(text: str) -> str:
    text_lower = text.lower()
    return ''.join(character for character in text_lower if character in string.ascii_lowercase)


def flatten_repost_lists_except_original(reposts: list[list[int]]) -> list[int]:
    return itertools.chain.from_iterable([repost_list[1:] for repost_list in reposts])


def _get_params_from_telegram_update(update: Update) -> RepostBotTelegramParams:
    effective_message = update.channel_post if update.channel_post is not None else update.effective_message
    effective_chat = effective_message.sender_chat
    sender_id = effective_chat.id if effective_chat is not None else effective_message.from_user.id
    sender_name = effective_chat.title if effective_chat is not None else effective_message.from_user.first_name
    group_id = effective_message.chat_id
    return RepostBotTelegramParams(group_id, sender_id, sender_name, effective_message)


def get_repost_params(func):
    @wraps(func)
    async def _wrapped(repostbot_instance, update: Update, context: CallbackContext, *args, **kwargs):
        return await func(repostbot_instance,
                          update,
                          context,
                          params=_get_params_from_telegram_update(update),
                          *args,
                          **kwargs)

    return _wrapped
