#!/usr/bin/env python3
"""Verify the contents of the monitor database."""
from multi_monitor.db import MonitorDB

def format_size(size_bytes):
    """Format bytes into human readable size."""
    if size_bytes is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024 or unit == 'GB':
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024

def main():
    db = MonitorDB('data/monitor.db')
    
    # 1. Check largest files
    print("\n=== Top 10 Largest Files ===")
    query = """
    SELECT r.name, r.url, s.content_length, s.status_code
    FROM resources r
    JOIN resource_status s ON r.id = s.resource_id
    WHERE s.content_length IS NOT NULL
    ORDER BY s.content_length DESC
    LIMIT 10
    """
    for name, url, size, status in db.conn.execute(query).fetchall():
        print(f"{name}: {format_size(size)} (HTTP {status})")
        print(f"  URL: {url}")

    # 2. Check linked resources
    print("\n=== Resources with Linked URLs ===")
    query = """
    SELECT r.name, r.url, 
           (SELECT COUNT(*) 
            FROM resources r2 
            WHERE r2.metadata->>'parent_resource_id' = r.id) as linked_count
    FROM resources r
    WHERE EXISTS (
        SELECT 1 FROM resources r2 
        WHERE r2.metadata->>'parent_resource_id' = r.id
    )
    ORDER BY linked_count DESC
    LIMIT 5
    """
    for name, url, count in db.conn.execute(query).fetchall():
        print(f"{name}: {count} linked URLs")
        print(f"  URL: {url}")

    # 3. Check status distribution
    print("\n=== Status Distribution ===")
    query = """
    SELECT status, COUNT(*) as count
    FROM resource_status
    GROUP BY status
    ORDER BY count DESC
    """
    for status, count in db.conn.execute(query).fetchall():
        print(f"{status}: {count}")

    # 4. Check response times
    print("\n=== Slowest Responses (>1s) ===")
    query = """
    SELECT r.name, r.url, s.response_time, s.status_code
    FROM resources r
    JOIN resource_status s ON r.id = s.resource_id
    WHERE s.response_time > 1.0
    ORDER BY s.response_time DESC
    LIMIT 5
    """
    for name, url, time, status in db.conn.execute(query).fetchall():
        print(f"{name}: {time:.2f}s (HTTP {status})")
        print(f"  URL: {url}")

    # 5. Check total data volume
    print("\n=== Total Data Volume ===")
    query = """
    SELECT 
        COUNT(*) as total_resources,
        COUNT(DISTINCT resource_id) as unique_resources,
        SUM(CASE WHEN content_length IS NOT NULL THEN 1 ELSE 0 END) as size_tracked,
        SUM(content_length) as total_bytes
    FROM resource_status
    """
    for total, unique, tracked, bytes_ in db.conn.execute(query).fetchall():
        print(f"Total Resources: {total}")
        print(f"Unique Resources: {unique}")
        print(f"Resources with Size: {tracked}")
        print(f"Total Data Volume: {format_size(bytes_)}")

    # 6. Enhanced content removal analysis
    print("\n=== Content Removal Analysis ===")
    
    # First get the main resources with stripped content
    query = """
    SELECT r.name, r.url, s.status, s.error_message, r.id
    FROM resources r
    JOIN resource_status s ON r.id = s.resource_id
    WHERE s.status = 'content_stripped'
       OR s.error_message LIKE '%executive order%'
       OR s.error_message LIKE '%under review%'
       OR s.error_message LIKE '%temporarily removed%'
       OR s.error_message LIKE '%content has been stripped%'
       OR s.error_message LIKE '%content removal%'
    ORDER BY r.name
    """
    results = db.conn.execute(query).fetchall()
    if not results:
        print("No content removal or stripping detected")
    else:
        for name, url, status, error, resource_id in results:
            print(f"\n{name}")
            print(f"  URL: {url}")
            print(f"  Status: {status}")
            if error:
                print(f"  Message: {error}")
            
            # Get linked resources with errors for this resource
            linked_query = """
            SELECT 
                r.name, 
                r.url, 
                s.status, 
                s.error_message,
                s.content_length,
                r.metadata
            FROM resources r
            JOIN resource_status s ON r.id = s.resource_id
            WHERE r.metadata->>'parent_resource_id' = ?
              AND (s.status = 'error' 
                   OR s.status = 'content_stripped'
                   OR s.error_message IS NOT NULL)
            LIMIT 5
            """
            linked_results = db.conn.execute(linked_query, (resource_id,)).fetchall()
            if linked_results:
                print("  Affected Linked Resources (up to 5):")
                for lname, lurl, lstatus, lerror, lcontent_length, lmetadata in linked_results:
                    print(f"    - {lname or lurl}")
                    if lerror:
                        print(f"      Error: {lerror}")
                    print(f"      Content Length: {format_size(lcontent_length) if lcontent_length else 'None'}")
                    print(f"      Metadata: {lmetadata}")

if __name__ == '__main__':
    main()
