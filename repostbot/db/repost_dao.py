import itertools
import sqlite3
from datetime import datetime
from sqlite3 import Row
from typing import Iterable, Callable


def group_by[T, K, V](iterable: Iterable[T],
                      key_mapper: Callable[[T], K],
                      value_mapper: Callable[[T], V] = lambda value: value) -> dict[K, list[V]]:
    return {
        key: [value_mapper(item) for item in values]
        for key, values
        in itertools.groupby(iterable, key_mapper)
    }


class RepostDAO:

    @staticmethod
    def get_group_reposts(group_id: int) -> dict[str, list[int]]:
        with sqlite3.connect('repostdb.sqlite') as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            repost_result: list[Row] = cursor.execute(
                'select hash_value, message_id from reposts where group_id = ? order by hash_value',
                (group_id,)
            ).fetchall()
            return group_by(repost_result, lambda row: row['hash_value'], lambda row: int(row['message_id']))

    @staticmethod
    def insert_reposts_for_group(group_id: int, user_id: int, message_id: int, hashes: Iterable[str]):
        with sqlite3.connect('repostdb.sqlite') as connection:
            cursor = connection.cursor()
            now = datetime.now()
            cursor.executemany(
                '''
                 insert into reposts(group_id, user_id, message_id, hash_value, hash_checked_date)
                 values (?, ?, ?, ?, ?)
                 ''',
                ((group_id, user_id, message_id, hash_value, now) for hash_value in hashes))

    @staticmethod
    def remove_all_for_group(group_id: int):
        with sqlite3.connect('repostdb.sqlite') as connection:
            cursor = connection.cursor()
            cursor.execute(
                'delete from reposts where group_id = ?',
                (group_id,)
            )
