import sqlite3
from sqlite3 import Row
from typing import Iterable


class DeletedMessagesDAO:

    @staticmethod
    def get_deleted_messages_for_group(group_id: int) -> set[int]:
        with sqlite3.connect('repostdb.sqlite') as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            result: list[Row] = cursor.execute(
                'select message_id from deleted_messages where group_id = ?',
                (group_id,)
            ).fetchall()
            return {int(row['message_id']) for row in result}

    @staticmethod
    def insert_deleted_message_for_group(group_id: int, message_id: int):
        with sqlite3.connect('repostdb.sqlite') as connection:
            cursor = connection.cursor()
            cursor.execute(
                'insert into deleted_messages(group_id, message_id) values (?, ?)',
                (group_id, message_id)
            )

    @staticmethod
    def insert_deleted_messages_for_group(group_id: int, message_ids: Iterable[int]):
        with sqlite3.connect('repostdb.sqlite') as connection:
            cursor = connection.cursor()
            cursor.executemany(
                'insert into deleted_messages(group_id, message_id) values (?, ?)',
                ((group_id, message_id) for message_id in message_ids)
            )

    @staticmethod
    def remove_all_deleted_message_records_for_group(group_id: int):
        with sqlite3.connect('repostdb.sqlite') as connection:
            cursor = connection.cursor()
            cursor.execute(
                'delete from deleted_messages where group_id = ?',
                (group_id,)
            )
