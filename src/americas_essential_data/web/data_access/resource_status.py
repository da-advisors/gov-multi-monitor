from .db import DatabaseInstance


class ResourceStatusRepository:
    def __init__(self, db: DatabaseInstance):
        self.db = db

    def find_latest_changes(self):
        # TODO: Swap this out with read of the new materialized view?
        return [
            dict(
                dataset="Workplace Fatality Investigations Data",
                source="Occupational Safety and Health Administration",
                status_type="resources_offline",
                count=4,
                updated_at="February 13, 2025 9:14 AM EST",
            ),
            dict(
                dataset="Demographic and Health Survey STATCompiler",
                source="U.S. Agency for International Development",
                status_type="source_offline",
                updated_at="February 12, 2025 12:30 AM EST",
            ),
            dict(
                dataset="American Community Survey",
                source="U.S. Census Bureau",
                status_type="resources_not_updated",
                count=2,
                updated_at="February 12, 2025 10:20 PM EST",
            ),
        ]

    def find_by_resource_id(self, resource_id):
        return self.db.query(
            """
            SELECT * FROM resource_status
            WHERE resource_id = ?
            ORDER BY checked_at DESC
            """,
            [resource_id],
        )
