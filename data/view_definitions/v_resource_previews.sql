CREATE VIEW v_resource_previews AS (
    SELECT 
        resources.*,
        resource_status.id as latest_status_id,
        resource_status.checked_at as latest_status_timestamp,
        resource_status.status as latest_status,
        resource_status.status_code as latest_status_code,
        resource_status.status_text as latest_status_text
    FROM
        resources
    LEFT JOIN
        v_latest_resource_status
        ON resources.id = v_latest_resource_status.resource_id
    LEFT JOIN
        resource_status
        ON v_latest_resource_status.id = resource_status.id
);