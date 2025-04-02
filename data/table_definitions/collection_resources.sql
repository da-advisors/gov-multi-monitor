CREATE TABLE IF NOT EXISTS collection_resources (
                id VARCHAR PRIMARY KEY,    -- UUID
                collection_id VARCHAR NOT NULL,
                resource_id VARCHAR NOT NULL,
                is_primary BOOLEAN,        -- Is this the primary resource for collection (at most 1 per collection)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP,        -- When removed from collection
                metadata JSON,             -- Including config_source, end_reason
                FOREIGN KEY (collection_id) REFERENCES collections(id),
                FOREIGN KEY (resource_id) REFERENCES resources(id)
            )