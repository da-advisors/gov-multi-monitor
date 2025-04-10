CREATE VIEW beta.v_collection_previews AS (
    WITH resource_counts AS (
        SELECT 
            collection_id,
            count(distinct(resource_id)) as linked_resources_count
        FROM
            beta.collection_resources
        GROUP BY 1
    ),
    primary_resources AS (
        SELECT
            collection_id,
            resource_id
        FROM
            beta.collection_resources
        WHERE is_primary = True
        -- TODO: Need to enforce that there is not more than 1 "primary" per collection
    )
    SELECT 
        collections.*,
        resource_counts.linked_resources_count,
        resources.url as primary_resource_url
        -- TODO: Add here any business logic for determining overall collection status
        --  from the constiuent resource statuses.
    FROM
        beta.collections
    LEFT JOIN
        resource_counts
        ON collections.id = resource_counts.collection_id
    LEFT JOIN
        primary_resources
        ON collections.id = primary_resources.collection_id
    LEFT JOIN
        beta.resources
        ON primary_resources.resource_id = resources.id
);