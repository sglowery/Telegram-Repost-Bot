from __future__ import annotations

from enum import Enum
from typing import Any

from .toggles import Toggles, ToggleType


class GroupDataKeys(Enum):
    TOGGLES = "toggles"


class GroupSettings:

    def __init__(self, data_dict: dict[str, Any]):
        self._dict = data_dict

    @staticmethod
    def blank(default_toggles: dict[ToggleType, bool]) -> GroupSettings:
        return GroupSettings({
            GroupDataKeys.TOGGLES.value: default_toggles,
        })

    @property
    def toggles(self) -> Toggles:
        return Toggles(self._dict.get(GroupDataKeys.TOGGLES.value))

    @toggles.setter
    def toggles(self, value: Toggles):
        self._dict[GroupDataKeys.TOGGLES.value] = value

    def to_dict(self) -> dict[str, Any]:
        return {
            GroupDataKeys.TOGGLES.value: self.toggles.as_dict(),
        }
