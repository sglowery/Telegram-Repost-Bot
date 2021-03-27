from typing import Optional, List


class GetMessageEntityHashesResult:
    def __init__(self, picture_key: Optional[str], url_keys: List[str]):
        self.picture_key = picture_key
        self.url_keys = url_keys
