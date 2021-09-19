import argparse
import locale
import logging

from config import get_config_variables
from repostbot import RepostBot
from repostitory import Repostitory
from strategies import STRATEGIES

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

logger = logging.getLogger(__name__)

locale.setlocale(locale.LC_ALL, 'en_US')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run an instance of Repost Bot over Telegram")
    parser.add_argument('-c', '--config', type=str, help='set path of config file relative to this file')
    args = parser.parse_args()
    config_path = args.config

    repost_data_path, bot_admin_id, telegram_token, default_callouts, bot_strings, hash_size, repost_callout_timeout, \
    auto_call_out, strategy, = get_config_variables(config_path)

    repost_repository = Repostitory(hash_size, repost_data_path, default_callouts)
    rpb = RepostBot(telegram_token, bot_strings, bot_admin_id, repost_repository, STRATEGIES.get(strategy),
                    auto_call_out, repost_callout_timeout)
    rpb.run()
