from __future__ import annotations

from typing import List, Dict, Iterable

_ALL_TOGGLES = {
    'picture': 'Track Pictures',
    'url': 'Track URLs',
}


class Toggles:

    def __init__(self, toggles_dict: Dict[str, bool]):
        self._toggles_dict = toggles_dict

    @property
    def track_pictures(self) -> bool:
        return self._toggles_dict.get('picture')

    @property
    def track_urls(self) -> bool:
        return self._toggles_dict.get('url')

    def as_json(self) -> Dict[str, bool]:
        return {
            'picture': self.track_pictures,
            'url': self.track_urls
        }

    def __getitem__(self, item: str) -> bool:
        return self._toggles_dict[item]

    def __setitem__(self, key: str, value: bool) -> None:
        self._toggles_dict[key] = value

    @staticmethod
    def get_toggle_args() -> List[str]:
        return list(_ALL_TOGGLES.keys())

    @staticmethod
    def get_toggle_display_name(toggle: str) -> str:
        return _ALL_TOGGLES[toggle]
