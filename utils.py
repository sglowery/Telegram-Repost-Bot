import logging
from datetime import datetime
from typing import Dict, Callable, NoReturn, List, TypeVar, ValuesView

from telegram import Update
from telegram.ext import CallbackContext

logger = logging.getLogger("Flood Protection")


_flood_track: Dict[int, Dict[str, datetime]] = dict()


def ignore_chat_type(chat_type: str):
    def _wrapped(func: Callable):
        def _continue_if_not_chat_type(repostbot_instance, update: Update, context: CallbackContext, *args, **kwargs):
            if update.message.chat.type != chat_type:
                return func(repostbot_instance, update, context, *args, **kwargs)
        return _continue_if_not_chat_type
    return _wrapped


def flood_protection(command_key: str):
    def _wrapped(func: Callable):
        def _check_track_and_call(repostbot_instance, update: Update, context: CallbackContext, *args, **kwargs):
            _init_tracking_for_user(update.effective_user.id)
            threshold = repostbot_instance.flood_protection_seconds
            last_called = _flood_track.get(update.message.from_user.id).get(command_key)
            if last_called is None or (datetime.now() - last_called).total_seconds() > threshold:
                _clean_up_tracking(threshold)
                _flood_track.get(update.message.from_user.id).update({command_key: datetime.now()})
                return func(repostbot_instance, update, context, *args, **kwargs)
            else:
                logger.info(f"Anti-flood protection on key {command_key}")
        return _check_track_and_call
    return _wrapped


def _init_tracking_for_user(user_id: int) -> NoReturn:
    if _flood_track.get(user_id) is None:
        _flood_track.update({user_id: dict()})


def _clean_up_tracking(threshold: int):
    now = datetime.now()
    new_track = {
        user_id: {
            command_key: last_command_called
            for command_key, last_command_called in _flood_track.get(user_id).items()
            if (now - last_command_called).total_seconds() > threshold
        }
        for user_id in _flood_track.keys()
    }
    _flood_track.clear()
    _flood_track.update(new_track)


def sum_list_lengths(lists: ValuesView) -> int:
    return sum(len(_list) for _list in lists)
