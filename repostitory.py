import hashlib
import json
import logging
import os
import time
from typing import List
from typing import NoReturn

from PIL import Image
from imagehash import average_hash
from telegram import Message
from telegram import MessageEntity

from repostbottypes import RepostDataStructure
from repostbottypes import RepostHashKeys
from repostbottypes import RepostSet
from repostbottypes import TrackStructure
from repostbottypes import WhitelistStructure
from whiteliststatus import WhitelistAddStatus

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

logger = logging.getLogger(__name__)


class Repostitory:

    def __init__(self, hash_size: int, data_path: str, default_callout_settings: TrackStructure):
        self.data_path = data_path
        self.default_callout_settings = default_callout_settings
        self.hash_size = hash_size
        self._check_directory()

    def get_repost_message_ids(self, message: Message) -> List[RepostSet]:
        message_id = message.message_id
        group_id = message.chat.id
        group_data = self.get_group_data(group_id)
        group_reposts = group_data.get("reposts")
        keys = self._get_repost_keys(message)
        reposts_in_message = list()
        for key in keys:
            list_of_message_ids = group_reposts.get(key, None)
            if list_of_message_ids is None or len(list_of_message_ids) == 0:
                logger.info("new picture or url detected")
                group_reposts.update({key: [message_id]})
            else:
                whitelist_data = group_data.get("whitelist", list())
                if key not in whitelist_data:
                    logger.info("REPOST DETECTED REEEE")
                    list_of_message_ids.append(message_id)
                    reposts_in_message.append(list_of_message_ids)
                else:
                    logger.info("Key is whitelisted; doing nothing")
        self.save_group_data(group_id, group_data)
        return reposts_in_message

    def save_group_data(self, group_id: str, new_group_data: RepostDataStructure) -> NoReturn:
        with open(self._get_group_path(group_id), 'w') as f:
            json.dump(new_group_data, f, indent=2)

    def get_group_data(self, cid: str) -> RepostDataStructure:
        self._ensure_group_file(cid)
        with open(self._get_group_path(cid)) as f:
            data: RepostDataStructure = json.load(f)
        return data

    def whitelist_repostable_in_message(self, message: Message) -> WhitelistAddStatus:
        group_data = self.get_group_data(message.chat.id)
        whitelisted_hashes: WhitelistStructure = group_data.get("whitelist", list())
        keys_in_message = self._get_repost_keys(message)
        if len(keys_in_message) > 0:
            key_removed = False
            for key in keys_in_message:
                if key in whitelisted_hashes:
                    whitelisted_hashes.remove(key)
                    key_removed = True
                else:
                    whitelisted_hashes.append(key)
            group_data["whitelist"] = whitelisted_hashes
            self.save_group_data(message.chat.id, group_data)
            if key_removed:
                return WhitelistAddStatus.ALREADY_EXISTS
            return WhitelistAddStatus.SUCCESS
        return WhitelistAddStatus.FAIL

    def reset_group_repost_data(self, cid: str) -> NoReturn:
        new_group_data: RepostDataStructure = {
            "track": self.default_callout_settings,
            "reposts": {},
            "whitelist": []
        }
        self.save_group_data(cid, new_group_data)

    def get_tracking_data(self, group_id: str):
        return self.get_group_data(group_id).get("track", self.default_callout_settings)

    def save_tracking_data(self, group_id: str, tracking_data: TrackStructure):
        group_data = self.get_group_data(group_id)
        current_tracking = group_data.get("track", self.default_callout_settings)
        new_tracking = {**current_tracking, **tracking_data}
        group_data.update({"track": new_tracking})
        self.save_group_data(group_id, group_data)

    def _ensure_group_file(self, cid: str) -> NoReturn:
        try:
            with open(self._get_group_path(cid)):
                pass
        except FileNotFoundError:
            logger.info("group has no file; making one")
            with open(self._get_group_path(cid), 'w') as f:
                json.dump({"track": self.default_callout_settings, "reposts": {}, "whitelist": []}, f, indent=2)

    def _get_repost_keys(self, message: Message) -> RepostHashKeys:
        keys = list()
        entities = message.parse_entities(types=[MessageEntity.URL])
        with open(self._get_group_path(message.chat.id)) as f:
            group_toggles = json.load(f).get("track")
        if message.photo and group_toggles["picture"]:
            photo = message.photo[-1]
            path = f"{photo.file_id}.jpg"
            old_time = time.process_time()
            logger.info("getting file...")
            message.bot.get_file(photo).download(path)
            logger.info(f"done (took {time.process_time() - old_time} seconds)")
            keys.append(str(average_hash(Image.open(path), hash_size=self.hash_size)))
            os.remove(path)
        if len(entities) and group_toggles["url"]:
            for entity in entities:
                keys.append(str(hashlib.sha256(
                    bytes(message.text[entity.offset: entity.offset + entity.length], 'utf-8')).hexdigest()))
        return keys

    # <group_id>.txt maps an image hash or url to a list of message ids that contain an image with that hash or url
    def _get_group_path(self, group_id: str):
        return f"{self.data_path}/{group_id}.json"

    def _get_repost_messages(self, group_id: str, key: str) -> RepostHashKeys:
        with open(self._get_group_path(group_id), 'r') as f:
            reposts = json.load(f).get("reposts")
        return reposts[key]

    def _check_directory(self) -> NoReturn:
        if not os.path.exists(self.data_path):
            os.makedirs(self.data_path)
