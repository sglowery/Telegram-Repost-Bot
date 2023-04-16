import hashlib
import logging
import os
from dataclasses import dataclass
from timeit import default_timer as timer

import ujson as json
from PIL import Image
from imagehash import average_hash
from telegram import Message
from telegram import MessageEntity

from repostbot.toggles import Toggles, ToggleType
from repostbot.whitelist_status import WhitelistAddStatus
from utils import RepostBotTelegramParams

logger = logging.getLogger("Repostitory")


@dataclass(frozen=True)
class MessageEntityHashes:
    picture_key: str | None
    url_keys: list[str]


class Repostitory:
    def __init__(self,
                 hash_size: int,
                 data_path: str,
                 default_toggles: dict[ToggleType, bool]):
        self.data_path = data_path
        self.default_toggles = default_toggles
        self.hash_size = hash_size
        self._check_directory()

    def process_message_entities(self, params: RepostBotTelegramParams) -> dict[str, list[int]]:
        chat_id = params.group_id
        self._ensure_group_file(chat_id)
        toggles = self.get_toggles_data(chat_id)
        message = params.effective_message
        hash_result = self.get_message_entity_hashes(message, toggles)
        picture_key = hash_result.picture_key
        url_keys = hash_result.url_keys
        message_id = message.message_id
        hashes = list()
        if picture_key is not None and toggles.track_pictures:
            hashes.append(picture_key)
        if toggles.track_urls:
            hashes.extend(url_keys)
        group_data = self._update_repost_data_for_group(chat_id, message_id, hashes)
        reposts = group_data.get("reposts", {})
        whitelist = group_data.get("whitelist", [])
        return {entity_hash: reposts.get(entity_hash, []) for entity_hash in hashes if entity_hash not in whitelist}

    def save_group_data(self, chat_id: int, new_group_data: dict) -> None:
        with open(self._get_path_for_group_data(chat_id), 'w') as f:
            json.dump(new_group_data, f, indent=2)

    def get_group_data(self, group_id: int) -> dict:
        self._ensure_group_file(group_id)
        with open(self._get_path_for_group_data(group_id)) as f:
            data = json.load(f)
        return data

    def process_whitelist_command(self, message: Message, group_id: int) -> WhitelistAddStatus:
        group_data = self.get_group_data(group_id)
        whitelisted_hashes: list[str] = group_data.get("whitelist", list())
        hashes = self.get_message_entity_hashes(message, self.get_toggles_data(group_id))
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
            self.save_group_data(group_id, group_data)
            if key_removed:
                return WhitelistAddStatus.ALREADY_EXISTS
            return WhitelistAddStatus.SUCCESS
        return WhitelistAddStatus.FAIL

    def reset_group_repost_data(self, group_id: int) -> None:
        self.save_group_data(group_id, self._get_empty_group_file_structure())

    def get_toggles_data(self, group_id: int) -> Toggles:
        toggles_dict = self.get_group_data(group_id).get("toggles", self.default_toggles)
        return Toggles(toggles_dict)

    def save_toggles_data(self, group_id: int, toggles: Toggles):
        group_data = self.get_group_data(group_id)
        current_toggles = group_data.get("toggles", self.default_toggles)
        new_toggles = {**current_toggles, **toggles.as_dict()}
        group_data.update({"toggles": new_toggles})
        self.save_group_data(group_id, group_data)

    def get_message_entity_hashes(self, message: Message, toggles: Toggles) -> MessageEntityHashes:
        picture_key = None
        url_keys = list()
        url_entities = message.parse_entities(types=[MessageEntity.URL])
        if message.photo and toggles.track_pictures:
            photo = message.photo[-1]
            path = f"{photo.file_id}.jpg"
            start_time = timer()
            logger.info("Getting file...")
            message.bot.get_file(photo).download(path)
            with Image.open(path) as f:
                picture_key = str(average_hash(f, hash_size=self.hash_size))
            end_time = timer()
            logger.info(f"Done (took {(end_time - start_time):.2f} seconds)")
            os.remove(path)
        if len(url_entities) > 0 and toggles.track_urls:
            for url_entity in url_entities:
                end_offset = url_entity.offset + url_entity.length
                url_hash = hashlib.sha256(bytes(message.text[url_entity.offset: end_offset], 'utf-8')).hexdigest()
                url_keys.append(url_hash)
        return MessageEntityHashes(picture_key, url_keys)

    def get_deleted_messages(self, group_id) -> list[int]:
        return self.get_group_data(group_id).get("deleted")

    def updated_deleted_messages(self, group_id: int, newly_deleted_messages: list[int]) -> None:
        group_data = self.get_group_data(group_id)
        group_data.get("deleted", []).extend(newly_deleted_messages)
        self.save_group_data(group_id, group_data)

    def _update_repost_data_for_group(self, group_id: int, message_id: int, hashes: list[str]) -> dict[str, Any]:
        group_data = self.get_group_data(group_id)
        group_reposts = group_data.get("reposts")
        for entity_hash in hashes:
            list_of_message_ids = group_reposts.get(entity_hash, None)
            if list_of_message_ids is None or len(list_of_message_ids) == 0:
                logger.info("New picture or url detected")
                group_reposts.update({entity_hash: [message_id]})
            else:
                list_of_message_ids.append(message_id)
        self.save_group_data(group_id, group_data)
        return group_data

    def _ensure_group_file(self, group_id: int) -> None:
        self._check_directory()
        try:
            with open(self._get_path_for_group_data(group_id)):
                pass
        except FileNotFoundError:
            logger.info("Group has no file; making one")
            with open(self._get_path_for_group_data(group_id), 'w') as f:
                json.dump(self._get_empty_group_file_structure(), f, indent=2)

    def _get_path_for_group_data(self, group_id: int | str) -> str:
        return f"{self.data_path}/{group_id}.json"

    def _check_directory(self) -> None:
        if not os.path.exists(self.data_path):
            os.makedirs(self.data_path)

    def _get_empty_group_file_structure(self) -> dict:
        return {
            "reposts": {},
            "toggles": self.default_toggles,
            "whitelist": [],
            "deleted": [],
        }
