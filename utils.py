import logging
from datetime import datetime
from typing import Dict, Callable, NoReturn

from telegram import Update
from telegram.ext import CallbackContext

logger = logging.getLogger("Flood Protection")


_flood_track: Dict[str, Dict[int, datetime]] = dict()


def ignore_chat_type(chat_type: str):
    def _wrapped(func: Callable):
        def _continue_if_not_chat_type(self, update: Update, context: CallbackContext, *args, **kwargs):
            if update.message.chat.type != chat_type:
                return func(self, update, context, *args, **kwargs)
        return _continue_if_not_chat_type
    return _wrapped


def flood_protection(command_key: str):
    def _wrapped(func: Callable):
        def _check_track_and_call(self, update: Update, context: CallbackContext, *args, **kwargs):
            _init_tracking_for_key(command_key)
            threshold = self.flood_protection_seconds
            last_called = _flood_track.get(command_key).get(update.message.from_user.id)
            if last_called is None or (datetime.now() - last_called).total_seconds() > threshold:
                _clean_up_tracking(threshold)
                _flood_track.get(command_key).update({update.message.from_user.id: datetime.now()})
                return func(self, update, context, *args, **kwargs)
            else:
                logger.info(f"Anti-flood protection on key {command_key}")
        return _check_track_and_call
    return _wrapped


def _init_tracking_for_key(key: str) -> NoReturn:
    if _flood_track.get(key) is None:
        _flood_track.update({key: dict()})


def _clean_up_tracking(threshold: int):
    now = datetime.now()
    new_track = {
        command_key: {
            user_id: last_command_called
            for user_id, last_command_called in _flood_track.get(command_key).items()
            if (now - last_command_called).total_seconds() > threshold
        }
        for command_key in _flood_track.keys()
    }
    _flood_track.clear()
    _flood_track.update(new_track)
