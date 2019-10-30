REPOST_ALERT_STRING = "!!! REPOST ALERT! REPOST ALERT !!!"
PRIVATE_CHAT_STRING = "I don't care about reposts just between us. I only check in group chats. Add me to a group ya " \
                      "dingus"
PRIVATE_CHAT_TOGGLE_STRING = "I don't track reposts in private chats."
HELP_STRING = "I'm {name}. I analyze the pictures and URLs you send and call out reposts. I store the message id, " \
              "and hashed versions of the URLs and pictures you send. GIFs and videos are not tracked."
REPOST_NOTIFIERS = ["FIRST POSTED HERE", "AND THEN HERE",
                    "REEEEEE ORIGINAL CONTENT PLEASE {name}!!!!!!!!!!!!!!!!! AAAAAAAAAAAA"]
INVALID_WHITELIST_REPLY = "Reply to a message containing a picture or URL you want whitelisted."
ALREADY_WHITELISTED_REPLY = "That's already whitelisted!"
SUCCESSFUL_WHITELIST_REPLY = "I won't track reposts of that from now on."
GROUP_REPOST_RESET_INITIAL_PROMPT = "Are you sure you want to delete the group's repost data? This is irreversible."
GROUP_REPOST_RESET_ADMIN_ONLY = "Only admins can do this action."
GROUP_REPOST_RESET_NO = "I won't delete it then."
GROUP_REPOST_DATA_RESET = "The group repost data has been reset."
GROUP_REPOST_PATH = "groups/"
DEFAULT_CALLOUT = {"url": True, "picture": True}
