from .db import DatabaseInstance


class ResourceRepository:
    def __init__(self, db: DatabaseInstance):
        self.db = db
        pass

    def all(self):
        return self.db.query(
            """
            SELECT * FROM resources
            """
        )

    def find_by_id(self, id):
        return self.db.query(
            """
            SELECT * FROM resources WHERE id = ?
            """,
            [id],
        )
