import argparse
import locale
import logging

from config import get_config_variables, get_environment_variables
from repostbot import RepostBot
from repostbot.repostitory import Repostitory
from repostbot.strategies import get_callout_strategy

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

logger = logging.getLogger(__name__)

locale.setlocale(locale.LC_ALL, 'en_US')


def main():
    parser = argparse.ArgumentParser(description='Run an instance of Repost Bot over Telegram')
    parser.add_argument('-c', '--config', type=str, help='set path of config file relative to this file')
    parser.add_argument('-e', '--environment', help='use environment variables to set API keys', action='store_true', dest='use_env')
    parser.set_defaults(use_env=False)
    args = parser.parse_args()
    config_path: str = args.config
    use_env: bool = args.use_env

    (
        telegram_token,
        bot_strings,
        bot_admin_id,
        strategy,
        flood_protection_timeout,
        hash_size,
        repost_data_path,
        default_toggles,
    ) = get_config_variables(config_path)

    if use_env:
        telegram_token, bot_admin_id = get_environment_variables()

    repostitory = Repostitory(hash_size, repost_data_path, default_toggles)
    rpb = RepostBot(
        telegram_token,
        bot_strings,
        bot_admin_id,
        get_callout_strategy(strategy),
        flood_protection_timeout,
        repostitory
    )
    rpb.run()


if __name__ == "__main__":
    main()
