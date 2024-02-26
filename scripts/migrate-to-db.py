import itertools
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any, Tuple

import yaml

try:
    import ujson as json
except ImportError:
    import json

type Repost = Tuple[int, int, str]

type Deleted = Tuple[int, int]

type Whitelisted = Tuple[int, str]


def _migrate_group_data_to_db():
    group_data_folder_name = None
    passed_argument = sys.argv[1] if len(sys.argv) > 1 else None
    config_paths = itertools.product(
        [file for file in [passed_argument, 'config.yaml', 'defaultconfig.yaml'] if file is not None],
        ['config', '../config', os.path.curdir, os.path.pardir]
    )
    for config_file_name, config_path in config_paths:
        try:
            path = os.path.abspath(config_path)
            joined = os.path.join(path, config_file_name)
            with open(joined) as f:
                group_data_folder_name = yaml.safe_load(f)['repost_data_path']
        except FileNotFoundError:
            pass
        else:
            print(f"Using config file located at {joined}")
            break
    if group_data_folder_name is None:
        raise RuntimeError("Couldn't find group data folder name from config files")
    else:
        print("\n\nFinding group data")
    try:
        path = os.path.abspath(group_data_folder_name)
        files = os.listdir(path)
    except FileNotFoundError:
        path = os.path.abspath(f'../{group_data_folder_name}')
        files = os.listdir(path)
    num_files = len(files)
    if num_files == 0:
        raise RuntimeError("Directory either doesn't have any files")
    elif not any(file[-5:] == '.json' for file in files):
        raise RuntimeError("Directory doesn't have any .json files")
    print(f"Using group data in {path}")
    files_done = 0
    files_migrated = 0
    error_files = 0
    to_migrate_reposts: list[Repost] = []
    to_migrate_whitelisted: list[Whitelisted] = []
    to_migrate_deleted: list[Deleted] = []
    for file in files:
        file_path = os.path.join(path, file)
        try:
            with open(file_path) as f:
                group_data: dict[str, Any] = json.load(f)
            group_id = int(file[:-5])
            reposts: dict[str, list[int]] | None = group_data.get('reposts')
            whitelist: list[str] | None = group_data.get('whitelist')
            deleted: list[int] | None = group_data.get('deleted')

            if (reposts is None) and (whitelist is None) and (deleted is None):
                print(f"{file} is already migrated")
                files_done += 1
                continue

            to_migrate_reposts.extend([
                (group_id, message_id, hash_value)
                for hash_value, message_ids in reposts.items()
                for message_id in message_ids
            ])
            to_migrate_whitelisted.extend(
                (group_id, whitelist_hash) for whitelist_hash in ([] if whitelist is None else whitelist))
            to_migrate_deleted.extend((group_id, message_id) for message_id in ([] if deleted is None else deleted))

            if reposts is not None:
                del group_data['reposts']
            if whitelist is not None:
                del group_data['whitelist']
            if deleted is not None:
                del group_data['deleted']
            with open(file_path, 'w') as f:
                json.dump(group_data, f)
            files_migrated += 1
            files_done += 1

        except Exception as e:
            error_files += 1
            print(f'whoopsie on {file}')
            raise e
        else:
            print(f"{file} migration complete")

    if len(to_migrate_reposts) + len(to_migrate_whitelisted) + len(to_migrate_deleted) == 0:
        print('nothing to migrate')
        return

    print('all files done. migrating to database.')
    with sqlite3.connect('repostdb.sqlite') as connection:
        cursor = connection.cursor()
        now = datetime.now()
        print('inserting reposts...', end='')
        cursor.executemany(
            'insert into reposts(group_id, user_id, message_id, hash_value, hash_checked_date) values (?, null, ?, ?, ?)',
            ((*repost_params, now) for repost_params in to_migrate_reposts)
        )
        print('done!')
        print('inserting whitelist...', end='')
        cursor.executemany(
            'insert into hash_whitelist(group_id, hash_value) values (?, ?)',
            to_migrate_whitelisted
        )
        print('done!')
        print('inserting deleted...', end='')
        cursor.executemany(
            'insert into deleted_messages(group_id, message_id) values (?, ?)',
            to_migrate_deleted
        )
    print('done migrating to the database.')


if __name__ == "__main__":
    _migrate_group_data_to_db()
