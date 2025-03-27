#!/usr/bin/env python3
"""
Migrate historical check results from GitHub Actions logs to DuckDB.
"""
import os
import re
from datetime import datetime, timezone
from typing import Dict, List

import requests
from tqdm import tqdm

from americas_essential_data.resource_monitor.db import MonitorDB


def fetch_workflow_runs(
    owner: str, repo: str, workflow_id: str, token: str
) -> List[Dict]:
    """Fetch all workflow runs for a specific workflow.

    Args:
        owner: Repository owner
        repo: Repository name
        workflow_id: Workflow ID or filename
        token: GitHub token with actions:read permission

    Returns:
        List of workflow runs
    """
    runs = []
    page = 1
    per_page = 100

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        params = {"page": page, "per_page": per_page}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        runs.extend(data["workflow_runs"])

        if len(data["workflow_runs"]) < per_page:
            break

        page += 1

    return runs


def fetch_run_logs(owner: str, repo: str, run_id: int, token: str) -> str:
    """Fetch logs for a specific workflow run.

    Args:
        owner: Repository owner
        repo: Repository name
        run_id: Run ID
        token: GitHub token with actions:read permission

    Returns:
        Log content as string
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    # First get the jobs for this run
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    jobs = response.json()["jobs"]
    if not jobs:
        return ""

    # Get logs for the first job (assuming it's the check job)
    job_id = jobs[0]["id"]
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.text


def parse_check_results(log_content: str) -> List[Dict]:
    """Parse check results from log content.

    Args:
        log_content: Raw log content

    Returns:
        List of check results
    """
    results = []
    current_result = None

    # Regular expressions for parsing - updated for actual log format
    url_pattern = r"(?:Checking URL|URL):\s*(.+)"
    status_pattern = r"(?:Status|Result):\s*(\w+)"
    code_pattern = r"(?:Status code|Code):\s*(\d+)"
    time_pattern = r"(?:Response time|Time):\s*([\d.]+)"
    modified_pattern = r"(?:Last modified|Modified):\s*(.+)"
    error_pattern = r"(?:Error|Exception|Failed):\s*(.+)"

    # Pattern for table format with Unicode box characters
    # Match lines like: │ Name │ https://... │ ok │ daily │ 2024-02-14 │ ok │ 3/3 │ View │
    table_row_pattern = r"[^│]+│\s*([^│]+)│\s*([^│]+)│\s*([^│]+)│\s*([^│]+)│\s*([^│]+)│\s*([^│]+)│\s*([^│]+)│\s*([^│]+)│"

    # Skip certain URLs that we don't want to track
    skip_urls = {"https://da-advisors.github.io/gov-multi-monitor/", "artifacts"}

    for line in log_content.split("\n"):
        line = line.strip()

        # Debug
        if (
            any(
                p in line.lower()
                for p in ["url", "status", "code", "time", "modified", "error"]
            )
            or "│" in line
        ):
            print(f"Potential match line: {line}")

        # Try to match table format first
        if table_match := re.search(table_row_pattern, line):
            name = table_match.group(1).strip()
            url = table_match.group(2).strip()
            status = table_match.group(3).strip().lower()
            expected_updates = table_match.group(4).strip()
            last_modified = table_match.group(5).strip()
            api_status = table_match.group(6).strip()
            linked_urls = table_match.group(7).strip()

            # Skip artifact URLs and deployment URLs
            if url.startswith("http") and not any(
                skip_url in url for skip_url in skip_urls
            ):
                if current_result:
                    results.append(current_result)
                    print(f"Added result: {current_result}")
                current_result = {
                    "url": url,
                    "timestamp": datetime.now(timezone.utc),
                    "status": status,
                    "name": name,
                    "expected_updates": expected_updates,
                    "last_modified": last_modified if last_modified != "-" else None,
                    "api_status": api_status if api_status != "-" else None,
                    "linked_urls": linked_urls if linked_urls != "-" else None,
                }
                print(
                    f"Found URL and status from table: {current_result['url']} -> {current_result['status']}"
                )
            continue

        # Start of new check (old format)
        if url_match := re.search(url_pattern, line, re.IGNORECASE):
            if current_result:
                # If we have a status code but no status, infer it
                if (
                    "status_code" in current_result
                    and current_result["status"] == "unknown"
                ):
                    code = current_result["status_code"]
                    if 200 <= code < 300:
                        current_result["status"] = "success"
                    elif 300 <= code < 400:
                        current_result["status"] = "redirect"
                    else:
                        current_result["status"] = "error"
                    print(f"Inferred status from code: {current_result['status']}")
                results.append(current_result)
                print(f"Added result: {current_result}")
            current_result = {
                "url": url_match.group(1).strip(),
                "timestamp": datetime.now(timezone.utc),
                "status": "unknown",  # Default status
            }
            print(f"Found URL: {current_result['url']}")

        # Parse check details
        elif current_result:
            if status_match := re.search(status_pattern, line, re.IGNORECASE):
                current_result["status"] = status_match.group(1).lower()
                print(f"Found status: {current_result['status']}")
            elif code_match := re.search(code_pattern, line, re.IGNORECASE):
                current_result["status_code"] = int(code_match.group(1))
                print(f"Found status code: {current_result['status_code']}")
            elif time_match := re.search(time_pattern, line, re.IGNORECASE):
                current_result["response_time"] = float(time_match.group(1))
                print(f"Found response time: {current_result['response_time']}")
            elif modified_match := re.search(modified_pattern, line, re.IGNORECASE):
                try:
                    current_result["last_modified"] = datetime.fromisoformat(
                        modified_match.group(1).strip()
                    )
                    print(f"Found last modified: {current_result['last_modified']}")
                except ValueError:
                    print(f"Could not parse date: {modified_match.group(1)}")
            elif error_match := re.search(error_pattern, line, re.IGNORECASE):
                current_result["error_message"] = error_match.group(1).strip()
                print(f"Found error: {current_result['error_message']}")

    # Add last result
    if current_result:
        # If we have a status code but no status, infer it
        if "status_code" in current_result and current_result["status"] == "unknown":
            code = current_result["status_code"]
            if 200 <= code < 300:
                current_result["status"] = "success"
            elif 300 <= code < 400:
                current_result["status"] = "redirect"
            else:
                current_result["status"] = "error"
            print(f"Inferred status from code: {current_result['status']}")
        results.append(current_result)
        print(f"Added final result: {current_result}")

    return results


def migrate_logs_to_db(
    owner: str, repo: str, workflow_id: str, token: str, db: MonitorDB
):
    """Migrate GitHub Actions logs to DuckDB.

    Args:
        owner: Repository owner
        repo: Repository name
        workflow_id: Workflow ID or filename
        token: GitHub token with actions:read permission
        db: Database connection
    """
    print("Fetching workflow runs...")
    runs = fetch_workflow_runs(owner, repo, workflow_id, token)

    print(f"Found {len(runs)} workflow runs")
    for run in tqdm(runs):
        print(f"\nProcessing run {run['id']} from {run['created_at']}")

        # Skip failed runs
        if run["conclusion"] != "success":
            print(f"Skipping failed run with conclusion: {run['conclusion']}")
            continue

        # Fetch and parse logs
        print("Fetching logs...")
        logs = fetch_run_logs(owner, repo, run["id"], token)
        print(f"Got {len(logs.splitlines())} lines of logs")

        print("Parsing results...")
        results = parse_check_results(logs)
        print(f"Found {len(results)} check results")

        if not results:
            print("Sample of logs:")
            print("\n".join(logs.splitlines()[:20]))
            continue

        # Add results to database
        print("Adding to database...")
        for result in results:
            url = result["url"]
            print(f"Processing result for {url}")

            # Find or create resource
            resource_query = db.conn.execute(
                "SELECT id FROM resources WHERE url = ?", [url]
            ).fetchone()

            if resource_query:
                resource_id = resource_query[0]
                print(f"Found existing resource: {resource_id}")
            else:
                print(f"Creating new resource with URL: {url}")
                resource_id = db.add_resource(
                    name=result.get(
                        "name", url
                    ),  # Use name if available, otherwise URL
                    type="url",
                    url=url,
                    metadata={"from_github_logs": True},
                )
                print(f"Created resource: {resource_id}")

            # Add status
            values = {
                "status_code": result.get("status_code"),
                "response_time": result.get("response_time"),
                "last_modified": result.get("last_modified"),
                "redirect_url": None,  # We don't have this in logs
                "content_hash": None,  # We don't have this in logs
            }
            # Filter out None values
            url_data = {k: v for k, v in values.items() if v is not None}

            status_id = db.add_resource_status(
                resource_id=resource_id,
                status=result["status"],
                checked_at=result["timestamp"],
                url_data=url_data,
                error_message=result.get("error_message"),
                metadata={"from_github_logs": True},
            )
            print(f"Added status: {status_id}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate GitHub Actions logs to DuckDB"
    )
    parser.add_argument("--owner", required=True, help="Repository owner")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--workflow", required=True, help="Workflow ID or filename")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub token with actions:read permission. Defaults to GITHUB_TOKEN environment variable.",
    )
    parser.add_argument(
        "--db", default="data/monitor.db", help="Path to DuckDB database"
    )

    args = parser.parse_args()

    if not args.token:
        parser.error(
            "No GitHub token provided. Either set GITHUB_TOKEN environment variable or use --token"
        )

    db = MonitorDB(args.db)
    migrate_logs_to_db(args.owner, args.repo, args.workflow, args.token, db)
