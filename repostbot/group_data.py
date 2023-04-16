from __future__ import annotations

from enum import Enum
from typing import Any

from .toggles import Toggles, ToggleType


class GroupDataKeys(Enum):
    REPOSTS = "reposts"
    WHITELIST = "whitelist"
    TOGGLES = "toggles"
    DELETED = "deleted"


class GroupData:

    def __init__(self, data_dict: dict[str, Any]):
        self._dict = data_dict

    @staticmethod
    def blank(default_toggles: dict[ToggleType, bool]) -> GroupData:
        return GroupData({
            GroupDataKeys.REPOSTS.value: dict(),
            GroupDataKeys.WHITELIST.value: set(),
            GroupDataKeys.TOGGLES.value: default_toggles,
            GroupDataKeys.DELETED.value: set(),
        })

    @property
    def reposts(self) -> dict[str, list[int]]:
        return self._dict.get(GroupDataKeys.REPOSTS.value, dict())

    @property
    def whitelist(self) -> set[str]:
        return set(self._dict.get(GroupDataKeys.WHITELIST.value, set()))

    @property
    def toggles(self) -> Toggles:
        return Toggles(self._dict.get(GroupDataKeys.TOGGLES.value))

    @property
    def deleted(self) -> set[int]:
        return set(self._dict.get(GroupDataKeys.DELETED.value, set()))

    def to_dict(self) -> dict[str, Any]:
        return {
            GroupDataKeys.REPOSTS.value: self.reposts,
            GroupDataKeys.WHITELIST.value: list(self.whitelist),
            GroupDataKeys.TOGGLES.value: self.toggles.as_dict(),
            GroupDataKeys.DELETED.value: list(self.deleted),
        }

    @whitelist.setter
    def whitelist(self, value: set[str]):
        self._dict[GroupDataKeys.WHITELIST.value] = set(value)

    @toggles.setter
    def toggles(self, value: Toggles):
        self._dict[GroupDataKeys.TOGGLES.value] = value

    @deleted.setter
    def deleted(self, value: set[int]):
        self._dict[GroupDataKeys.DELETED.value] = value
