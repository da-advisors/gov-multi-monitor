CREATE MATERIALIZED VIEW v_latest_resource_status AS (
    WITH rank_list AS(
        SELECT
            resource_id,
            id,
            checked_at, 
            rank() OVER (PARTITION BY resource_id ORDER BY checked_at desc) as ranking
        FROM resource_status
    )
    SELECT *
    FROM rank_list
    WHERE ranking = 1
);