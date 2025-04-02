CREATE TABLE IF NOT EXISTS collections (
                id VARCHAR PRIMARY KEY,    -- UUID
                name TEXT NOT NULL,
                description TEXT,
                metadata JSON,             -- Flexible metadata
                tags JSON,                 -- Collection tags
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                omb_control_number TEXT    -- OMB reference, for external reference data
            )