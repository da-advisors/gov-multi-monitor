import psycopg
import os

from typing import List


class DatabaseInstance:
    def __init__(self, path):
        # TODO: use `with` syntax or other handling for closing connection safely
        self.conn = psycopg.connect(
            database=os.environ.get("AES_DB_NAME"),
            user=os.environ.get("AES_DB_USER"),
            password=os.environ.get("AES_DB_PASSWORD"),
            host=os.environ.get("AES_DB_HOST"),
            port=os.environ.get("AES_DB_PORT"),
        )

    def query(self, query: object, parameters: object = None) -> List[tuple]:
        with self.conn.cursor() as cur:
            result = cur.execute(query, parameters)

        column_names = [column[0] for column in result.description]
        list_of_objects = [dict(zip(column_names, row)) for row in result.fetchall()]

        return list_of_objects
