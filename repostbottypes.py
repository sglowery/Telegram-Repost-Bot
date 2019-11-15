from typing import Dict
from typing import List

RepostSet = List[int]
ConversationState = int
TrackStructure = Dict[str, bool]
RepostStructure = Dict[str, RepostSet]
WhitelistStructure = List[str]
RepostHashKey = str
RepostHashKeys = List[str]
RepostDataStructure = Dict[str, TrackStructure and RepostStructure and WhitelistStructure]
