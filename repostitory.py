import hashlib
import json
import logging
import os
import time
from typing import List, Dict, Optional
from typing import NoReturn

from PIL import Image
from imagehash import average_hash
from telegram import Message
from telegram import MessageEntity

from whitelist_status import WhitelistAddStatus

logger = logging.getLogger("Repostitory")


class GetMessageEntityHashesResult:
    def __init__(self, picture_key: Optional[str], url_keys: List[str]):
        self.picture_key = picture_key
        self.url_keys = url_keys


class Repostitory:
    def __init__(self, hash_size: int, data_path: str, default_callout_settings: Dict[str, bool]):
        self.data_path = data_path
        self.default_callout_settings = default_callout_settings
        self.hash_size = hash_size
        self._check_directory()

    def process_message_entities(self, message: Message) -> Dict[str, List[int]]:
        chat_id = message.chat_id
        self._ensure_group_file(chat_id)
        group_data = self.get_group_data(chat_id)
        hash_result = self.get_message_entity_hashes(message)
        picture_key = hash_result.picture_key
        url_keys = hash_result.url_keys
        toggles = group_data.get("track", self.default_callout_settings)
        message_id = message.message_id
        hashes = list()
        self._update_repost_data_for_group(url_keys, message_id, chat_id)
        if picture_key is not None:
            self._update_repost_data_for_group([picture_key], message_id, chat_id)
            if toggles["picture"]:
                hashes.append(picture_key)
        if toggles["url"]:
            hashes.extend(url_keys)
        group_data = self.get_group_data(chat_id)
        reposts = group_data.get("reposts", {})
        whitelist = group_data.get("whitelist", [])
        return {entity_hash: reposts.get(entity_hash, []) for entity_hash in hashes if entity_hash not in whitelist}

    def save_group_data(self, chat_id: int, new_group_data) -> NoReturn:
        with open(self._get_path_for_group_data(chat_id), 'w') as f:
            json.dump(new_group_data, f, indent=2)

    def get_group_data(self, group_id: int) -> dict:
        self._ensure_group_file(group_id)
        with open(self._get_path_for_group_data(group_id)) as f:
            data = json.load(f)
        return data

    def process_whitelist_command_on_message(self, message: Message) -> WhitelistAddStatus:
        group_data = self.get_group_data(message.chat.id)
        whitelisted_hashes: List[str] = group_data.get("whitelist", list())
        hashes = self._get_message_entity_hashes(message)
        picture_key = hashes.picture_key
        url_keys = hashes.url_keys
        keys_in_message = [picture_key, *url_keys] if picture_key is not None else url_keys
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

    def reset_group_repost_data(self, group_id: int) -> NoReturn:
        self.save_group_data(group_id, self._get_empty_group_file_structure())

    def get_tracking_data(self, group_id: int):
        return self.get_group_data(group_id).get("track", self.default_callout_settings)

    def save_tracking_data(self, group_id: int, tracking_data: Dict[str, bool]):
        group_data = self.get_group_data(group_id)
        current_tracking = group_data.get("track", self.default_callout_settings)
        new_tracking = {**current_tracking, **tracking_data}
        group_data.update({"track": new_tracking})
        self.save_group_data(group_id, group_data)

    def get_message_entity_hashes(self, message: Message) -> GetMessageEntityHashesResult:
        picture_key = None
        url_keys = list()
        url_entities = message.parse_entities(types=[MessageEntity.URL])
        if message.photo:
            photo = message.photo[-1]
            path = f"{photo.file_id}.jpg"
            old_time = time.process_time()
            logger.info("getting file...")
            message.bot.get_file(photo).download(path)
            logger.info(f"done (took {time.process_time() - old_time} seconds)")
            picture_key = str(average_hash(Image.open(path), hash_size=self.hash_size))
            os.remove(path)
        if len(url_entities) > 0:
            for url_entity in url_entities:
                end_offset = url_entity.offset + url_entity.length
                url_keys.append(hashlib.sha256(bytes(message.text[url_entity.offset: end_offset], 'utf-8')).hexdigest())
        return GetMessageEntityHashesResult(picture_key, url_keys)

    def _update_repost_data_for_group(self, hashes: List[str], message_id: int, group_id: int) -> NoReturn:
        group_data = self.get_group_data(group_id)
        group_reposts = group_data.get("reposts")
        for entity_hash in hashes:
            list_of_message_ids = group_reposts.get(entity_hash, None)
            if list_of_message_ids is None or len(list_of_message_ids) == 0:
                logger.info("new picture or url detected")
                group_reposts.update({entity_hash: [message_id]})
            else:
                list_of_message_ids.append(message_id)
        self.save_group_data(group_id, group_data)

    def _ensure_group_file(self, group_id: int) -> NoReturn:
        self._check_directory()
        try:
            with open(self._get_path_for_group_data(group_id)):
                pass
        except FileNotFoundError:
            logger.info("group has no file; making one")
            with open(self._get_path_for_group_data(group_id), 'w') as f:
                json.dump(self._get_empty_group_file_structure(), f, indent=2)

    def _get_path_for_group_data(self, group_id: int) -> str:
        return f"{self.data_path}/{group_id}.json"

    def _check_directory(self) -> NoReturn:
        if not os.path.exists(self.data_path):
            os.makedirs(self.data_path)

    def _get_empty_group_file_structure(self) -> dict:
        return {"track": self.default_callout_settings, "reposts": {}, "whitelist": []}
