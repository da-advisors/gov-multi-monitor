from .db import DatabaseInstance


class CollectionRepository:
    def __init__(self, db: DatabaseInstance):
        self.db = db
        pass

    def all(self):
        return self.db.query(
            """
            SELECT * FROM collections;
            """
        )

    def find_by_id(self, id: str):
        return self.db.query(
            """
            SELECT * FROM collections WHERE id = ?;
            """,
            [id],
        )

    def all_previews(self):
        return self.db.query(
            """
            SELECT * FROM v_collection_previews;
            """
        )

    def find_resources_by_collection_id(self, collection_id: str):
        return self.db.query(
            """
            WITH linkages AS (
                SELECT
                    collection_id,
                    resource_id,
                    is_primary
                FROM collections_resources
                WHERE collection_id = ?
            )
            SELECT 
                resources.*,
                linkages.is_primary 
            FROM resources
            LEFT JOIN
                linkages
                ON resources.id = linkages.resource_id;
            """,
            [collection_id],
        )
