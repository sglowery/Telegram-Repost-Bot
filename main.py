import argparse
import locale
import logging

from config import get_config_variables
from repostbot.repostbot import RepostBot
from repostbot.strategies import STRATEGIES

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

logger = logging.getLogger(__name__)

locale.setlocale(locale.LC_ALL, 'en_US')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run an instance of Repost Bot over Telegram")
    parser.add_argument('-c', '--config', type=str, help='set path of config file relative to this file')
    args = parser.parse_args()
    config_path = args.config

    telegram_token, bot_strings, bot_admin_id, strategy, auto_call_out, repost_callout_timeout, hash_size, \
    repost_data_path, default_callouts = get_config_variables(config_path)

    rpb = RepostBot(telegram_token, bot_strings, bot_admin_id, STRATEGIES.get(strategy), auto_call_out,
                    repost_callout_timeout, hash_size, repost_data_path, default_callouts)
    rpb.run()
