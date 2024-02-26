from enum import Enum


class WhitelistAddStatus(Enum):
    SUCCESS = 1
    FAIL = 2
    ALREADY_EXISTS = 3
    ADDED_AND_REMOVED = 4
