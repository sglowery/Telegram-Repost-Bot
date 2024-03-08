import logging
import os
from typing import Any

import yaml
from dotenv import dotenv_values

from repostbot.strategies import get_all_callout_strategies, get_default_strategy

logger = logging.getLogger(__name__)


class MissingConfigParameterException(Exception):
    pass


class NoConfigFileAvailableException(Exception):
    pass


class MutuallyExclusiveParametersException(Exception):
    pass


def _ensure_proper_config_structure(data: dict[str, Any]):
    top_level = [
        "repost_data_path",
        "bot_admin_id",
        "bot_token",
        "hash_size",
        "flood_protection_timeout",
        "callout_style",
        "default_toggles",
        "strings",
        "group_whitelist",
        "group_blacklist",
    ]
    toggles = ["url", "picture", "autocallout", "autodelete"]
    strings = [
        "private_chat",
        "private_chat_toggle",
        "help_command",
        "settings_command_response",
        "enabled",
        "disabled",
        "settings_track_pictures",
        "settings_track_urls",
        "settings_auto_callout",
        "settings_auto_delete",
        "invalid_whitelist_reply",
        "removed_from_whitelist_reply",
        "added_and_removed_from_whitelist_reply",
        "successful_whitelist_reply",
        "group_repost_reset_initial_prompt",
        "group_reset_yes",
        "group_reset_no",
        "group_reset_confirmation_responses",
        "group_repost_reset_admin_only",
        "group_repost_reset_cancel",
        "group_repost_data_reset",
        "stats_command_reply",
        "blacklisted_response",
        "not_in_whitelist_response",
    ]
    for repost_strategy in get_all_callout_strategies():
        strings.extend(repost_strategy.get_required_strings())

    logger.info("TESTING TOP-LEVEL FIELDS")
    _check_config_fields(data, top_level, "top level fields")

    logger.info("TESTING DEFAULT TOGGLED SETTINGS")
    _check_config_fields(data.get("default_toggles"), toggles, "default toggles")

    logger.info("TESTING BOT STRINGS")
    _check_config_fields(data.get("strings"), strings, "strings")


def _check_config_fields(data: dict[str, Any], strings: list[str], field_type: str):
    if data is None:
        logger.warning(f"Data is missing for {field_type}")
        return
    for field in strings:
        value_exists = data.get(field) is not None
        logger_fn = logger.info if value_exists else logger.warning
        logger_fn(f"TESTING \"{field}\"...{'FOUND' if value_exists else 'UNDEFINED'}")


def get_config_variables(config_path: str) -> tuple:
    config_data, default_config_data = None, None

    if config_path is not None:
        try:
            with open(config_path) as f:
                config_data = yaml.safe_load(f)
        except (FileNotFoundError, TypeError) as e:
            logger.warning(f"{e.strerror} -- could not find '{config_path}'")
    else:
        logger.warning("User-created config not specified. Proceeding with defaultconfig.yaml")
    try:
        with open('config/defaultconfig.yaml', 'r') as f:
            default_config_data = yaml.safe_load(f)
    except (FileNotFoundError, TypeError) as e:
        if config_path is None:
            raise NoConfigFileAvailableException("Default config not found and no user-created config specified. Guess I'll die.")
        else:
            logger.warning("Could not find defaultconfig.yaml. If your config.yaml is missing anything, this could be an issue.")

    default_telegram_token = None
    default_bot_strings = dict()
    default_bot_admin_id = None
    default_strategy = None
    default_flood_protection_timeout = None
    default_hash_size = None
    default_repost_data_path = None
    default_default_toggles = None
    default_group_whitelist = None
    default_group_blacklist = None

    if default_config_data is not None:
        logger.info("testing default config file for all required fields")
        _ensure_proper_config_structure(default_config_data)
        default_telegram_token = default_config_data.get("bot_token", None)
        default_bot_strings = default_config_data.get("strings", {})
        default_bot_admin_id = default_config_data.get("bot_admin_id", None)
        default_strategy = default_config_data.get("callout_style", get_default_strategy())
        default_flood_protection_timeout = default_config_data.get("flood_protection_timeout", None)
        default_hash_size = default_config_data.get("hash_size", None)
        default_repost_data_path = default_config_data.get("repost_data_path", None)
        default_default_toggles = default_config_data.get("default_toggles", None)
        default_group_whitelist = default_config_data.get("group_whitelist", [])
        default_group_blacklist = default_config_data.get("group_blacklist", [])

    telegram_token = default_telegram_token
    bot_strings = default_bot_strings
    bot_admin_id = default_bot_admin_id
    strategy = default_strategy
    flood_protection_timeout = default_flood_protection_timeout
    hash_size = default_hash_size
    repost_data_path = default_repost_data_path
    default_toggles = default_default_toggles
    group_whitelist = default_group_whitelist
    group_blacklist = default_group_blacklist

    if config_path is not None and config_data is not None:
        logger.info("testing user config file for all required fields")
        _ensure_proper_config_structure(config_data)
        telegram_token = config_data.get("bot_token", default_telegram_token)
        bot_strings = {**default_bot_strings, **config_data.get("strings", {})}
        bot_admin_id = config_data.get("bot_admin_id", default_bot_admin_id)
        strategy = config_data.get("callout_style", default_strategy)
        flood_protection_timeout = config_data.get("flood_protection_timeout", default_flood_protection_timeout)
        hash_size = config_data.get("hash_size", default_hash_size)
        repost_data_path = config_data.get("repost_data_path", default_repost_data_path)
        default_toggles = config_data.get("default_toggles", default_default_toggles)
        group_whitelist = config_data.get("group_whitelist", default_group_whitelist)
        group_blacklist = config_data.get("group_blacklist", default_group_blacklist)

    bot_variables = (
        bot_strings,
        strategy,
        flood_protection_timeout,
        hash_size,
        repost_data_path,
        default_toggles,
        group_whitelist,
        group_blacklist,
    )
    if any(var is None for var in bot_variables):
        raise MissingConfigParameterException("Missing required config parameters between default and user config files. Cannot proceed.")

    if any(var is None for var in [telegram_token, bot_admin_id]):
        logger.warning("Missing Telegram token and bot admin ID; if using environment variables, this is fine.")

    if (len(group_whitelist) > 0) and (len(group_blacklist) > 0):
        raise MutuallyExclusiveParametersException("Whitelist and blacklist both have values defined. You can only use one list or neither of them.")

    return (
        telegram_token,
        bot_strings,
        bot_admin_id,
        strategy,
        flood_protection_timeout,
        hash_size,
        repost_data_path,
        default_toggles,
        group_whitelist,
        group_blacklist,
    )


def get_environment_variables():
    logger.info("Getting Telegram token and bot admin ID from environment variables")
    env_variables = {
        **dotenv_values(),
        **os.environ
    }
    telegram_token = env_variables.get("TELEGRAM_TOKEN")
    bot_admin_id = env_variables.get("BOT_ADMIN_ID")

    if telegram_token is None or bot_admin_id is None:
        raise MissingConfigParameterException("Failed to load Telegram token from environment variable, can't proceed.")

    return telegram_token, bot_admin_id
