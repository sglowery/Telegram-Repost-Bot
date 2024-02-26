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

from repostbot.db.deleted_messages_dao import DeletedMessagesDAO
from repostbot.db.hash_whitelist_dao import HashWhitelistDAO
from repostbot.db.repost_dao import RepostDAO
from repostbot.group_settings import GroupSettings
from repostbot.toggles import Toggles, ToggleType
from repostbot.whitelist_status import WhitelistAddStatus
from utils import RepostBotTelegramParams

logger = logging.getLogger("Repostitory")


@dataclass(frozen=True)
class MessageEntityHashes:
    picture_hash: str | None
    url_hashes: set[str]

    def __len__(self):
        return len(self.url_hashes) + (1 if self.picture_hash else 0)


class Repostitory:
    def __init__(self,
                 hash_size: int,
                 data_path: str,
                 default_toggles: dict[ToggleType, bool]):
        self.data_path = data_path
        self.default_toggles = default_toggles
        self.hash_size = hash_size
        self._check_directory()

    async def process_message_entities(self, params: RepostBotTelegramParams) -> dict[str, list[int]]:
        group_id = params.group_id
        self._ensure_group_file(group_id)
        message = params.effective_message
        hash_result = await self.get_message_entity_hashes(message)
        picture_key = hash_result.picture_hash
        url_keys = hash_result.url_hashes
        message_id = message.message_id
        hashes = set()
        toggles = self.get_toggles_data(group_id)
        if picture_key is not None and toggles.track_pictures:
            hashes.add(picture_key)
        if toggles.track_urls:
            hashes.update(url_keys)
        user_id = message.from_user.id
        # optimize the next two lines. insert_then_retrieve or something
        RepostDAO.insert_reposts_for_group(group_id, user_id, message_id, hashes)
        reposts = RepostDAO.get_group_reposts(group_id)
        whitelist = HashWhitelistDAO.get_whitelisted_hashes_for_group(group_id)
        return {
            entity_hash: reposts.get(entity_hash, [])
            for entity_hash in hashes
            if entity_hash not in whitelist
        }

    def save_group_data(self, group_id: int, new_group_data: GroupSettings) -> None:
        with open(self._get_path_for_group_data(group_id), 'w') as f:
            json.dump(new_group_data.to_dict(), f, indent=2)

    def get_group_data_json(self, group_id: int) -> GroupSettings:
        self._ensure_group_file(group_id)
        with open(self._get_path_for_group_data(group_id)) as f:
            data = json.load(f)
        return GroupSettings(data)

    def get_group_reposts(self, group_id: int) -> dict[str, list[int]]:
        return RepostDAO.get_group_reposts(group_id)

    async def process_whitelist_command(self, message: Message, group_id: int) -> WhitelistAddStatus:
        whitelisted_hashes: set[str] = HashWhitelistDAO.get_whitelisted_hashes_for_group(group_id)
        hashes = await self.get_message_entity_hashes(message)
        if len(hashes) == 0:
            return WhitelistAddStatus.FAIL
        picture_key = hashes.picture_hash
        url_keys = hashes.url_hashes
        keys_in_message: set[str] = {picture_key, *url_keys} if picture_key is not None else set(url_keys)
        message_keys_to_add = keys_in_message.difference(whitelisted_hashes)
        message_keys_to_remove = keys_in_message.intersection(whitelisted_hashes)

        hashes_were_removed = len(message_keys_to_remove) > 0
        if hashes_were_removed:
            HashWhitelistDAO.remove_all_whitelist_hashes_for_group(group_id)

        hashes_should_be_added = len(message_keys_to_add) > 0
        if hashes_should_be_added:
            HashWhitelistDAO.insert_whitelist_hashes_for_group(group_id, message_keys_to_add)

        match hashes_were_removed, hashes_should_be_added:
            case True, False:
                return WhitelistAddStatus.ALREADY_EXISTS
            case False, True:
                return WhitelistAddStatus.SUCCESS
            case True, True:
                return WhitelistAddStatus.ADDED_AND_REMOVED
            case _:
                return WhitelistAddStatus.FAIL

    def reset_group_repost_data(self, group_id: int) -> None:
        self.save_group_data(group_id, self._get_empty_group_file_structure())
        RepostDAO.remove_all_for_group(group_id)
        HashWhitelistDAO.remove_all_whitelist_hashes_for_group(group_id)
        DeletedMessagesDAO.remove_all_deleted_message_records_for_group(group_id)

    def get_toggles_data(self, group_id: int) -> Toggles:
        return self.get_group_data_json(group_id).toggles

    def save_toggles_data(self, group_id: int, toggles: Toggles):
        group_data = self.get_group_data_json(group_id)
        current_toggles = group_data.toggles
        new_toggles = {**current_toggles.as_dict(), **toggles.as_dict()}
        group_data.toggles = new_toggles
        self.save_group_data(group_id, group_data)

    async def get_message_entity_hashes(self, message: Message) -> MessageEntityHashes:
        picture_hash = None
        if message.photo:
            photo = message.photo[-1]
            path = f"{photo.file_id}.jpg"
            start_time = timer()
            logger.info("Getting file...")
            file = await message.get_bot().get_file(photo)
            await file.download_to_drive(path)
            end_time = timer()
            logger.info(f"Done (took {(end_time - start_time):.2f} seconds)")
            with Image.open(path) as f:
                picture_hash = str(average_hash(f, hash_size=self.hash_size))
            os.remove(path)

        url_message_entity_types = [MessageEntity.URL, MessageEntity.TEXT_LINK]
        message_urls = set(message.parse_entities(types=url_message_entity_types).values())
        caption_urls = set(message.parse_caption_entities(types=url_message_entity_types).values())
        urls = message_urls.union(caption_urls)
        url_hashes = {hashlib.sha256(bytes(url, 'utf-8')).hexdigest() for url in urls}

        return MessageEntityHashes(picture_hash, url_hashes)

    def get_deleted_messages(self, group_id) -> set[int]:
        return DeletedMessagesDAO.get_deleted_messages_for_group(group_id)

    def updated_deleted_messages(self, group_id: int, newly_deleted_messages: set[int]) -> None:
        DeletedMessagesDAO.insert_deleted_messages_for_group(group_id, newly_deleted_messages)

    def _ensure_group_file(self, group_id: int) -> None:
        self._check_directory()
        if not os.path.isfile(self._get_path_for_group_data(group_id)):
            logger.info("Group has no file; making one")
            with open(self._get_path_for_group_data(group_id), 'w') as f:
                json.dump(self._get_empty_group_file_structure().to_dict(), f, indent=2)

    def _get_path_for_group_data(self, group_id: int | str) -> str:
        return f"{self.data_path}/{group_id}.json"

    def _check_directory(self) -> None:
        if not os.path.exists(self.data_path):
            os.makedirs(self.data_path)

    def _get_empty_group_file_structure(self) -> GroupSettings:
        return GroupSettings.blank(self.default_toggles)
