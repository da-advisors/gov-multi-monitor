CREATE TABLE IF NOT EXISTS resources (
                id VARCHAR PRIMARY KEY,    -- UUID
                name TEXT NOT NULL,
                type TEXT NOT NULL,        -- 'url' or 'api_field'
                url TEXT,                  -- NULL for api_fields
                description TEXT,          -- Optional explanation of the resource
                metadata JSON,             -- Flexible metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );