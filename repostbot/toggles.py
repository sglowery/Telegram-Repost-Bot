from __future__ import annotations

from enum import Enum, unique
from typing import ItemsView


@unique
class ToggleType(Enum):
    PICTURE = 'picture'
    URL = 'url'
    AUTOCALLOUT = 'autocallout'
    AUTODELETE = 'autodelete'

    @staticmethod
    def from_value(value: str) -> ToggleType:
        for string_key, member in ToggleType.__members__.items():
            if value == member.value:
                return member
        raise ValueError(f"No matching value found in ToggleType: ${value}")


_TOGGLE_STRING_KEYS = {
    ToggleType.PICTURE: 'settings_track_pictures',
    ToggleType.URL: 'settings_track_urls',
    ToggleType.AUTOCALLOUT: 'settings_auto_callout',
    ToggleType.AUTODELETE: 'settings_auto_delete'
}


class Toggles:

    def __init__(self, toggles_dict: dict[str, bool]):
        self._toggles_dict = toggles_dict

    @property
    def track_pictures(self) -> bool:
        return self._toggles_dict.get(ToggleType.PICTURE.value)

    @property
    def track_urls(self) -> bool:
        return self._toggles_dict.get(ToggleType.URL.value)

    @property
    def auto_callout(self) -> bool:
        return self._toggles_dict.get(ToggleType.AUTOCALLOUT.value)

    @property
    def auto_delete(self) -> bool:
        return self._toggles_dict.get(ToggleType.AUTODELETE.value)

    def merged(self, other: Toggles) -> Toggles:
        return Toggles({**other._toggles_dict, **self._toggles_dict})

    def as_dict(self) -> dict[str, bool]:
        return {member.value: self[member] for _, member in ToggleType.__members__.items()}

    def __getitem__(self, item: ToggleType | str) -> bool:
        match item:
            case str():
                return self._toggles_dict[item]
            case ToggleType():
                return self._toggles_dict[item.value]

    def __setitem__(self, key: ToggleType, value: bool) -> None:
        self._toggles_dict[key.value] = value

    @staticmethod
    def get_toggle_args() -> ItemsView[ToggleType, str]:
        return {member: member.value for _, member in ToggleType.__members__.items()}.items()

    @staticmethod
    def get_toggle_display_name(toggle: ToggleType, strings: dict[str, str | list[str]]) -> str:
        return strings[_TOGGLE_STRING_KEYS[toggle]]
