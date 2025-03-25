import duckdb
from typing import List


class DatabaseInstance:
    def __init__(self, path):
        self.conn = duckdb.connect(str(path), read_only=True)

    def query(self, query: object, parameters: object = None) -> List[tuple]:
        result = self.conn.execute(query, parameters)
        column_names = [column[0] for column in result.description]
        list_of_objects = [dict(zip(column_names, row)) for row in result.fetchall()]

        return list_of_objects
