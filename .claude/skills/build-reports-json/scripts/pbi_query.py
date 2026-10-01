#!/usr/bin/env python3
"""
Power BI Service read-only query helper for the build-reports-json skill.
Performs only GET requests — never modifies anything in Power BI Service.

Commands:
  list-reports    --workspace-id <id>
  get-parameters  --workspace-id <id> --dataset-id <id>
  report-info     --workspace-id <id> [--report-name <name> | --all]

All output is JSON to stdout. Errors go to stderr with a non-zero exit code.
"""

import sys
import json
import argparse
import os
import stat
import requests
import msal

CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"  # Microsoft's public Power BI client
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]
BASE_URL = "https://api.powerbi.com/v1.0/myorg"

# Token cache stored outside the repo, readable only by the current OS user.
CACHE_FILE = os.path.join(os.path.expanduser("~"), ".pbi_tool_cache.json")


def _load_cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache.deserialize(f.read())
    return cache


def _save_cache(cache):
    if cache.has_state_changed:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(cache.serialize())
        # Restrict permissions to owner read/write only (600)
        os.chmod(CACHE_FILE, stat.S_IRUSR | stat.S_IWUSR)


def authenticate():
    """
    Authenticates via interactive browser pop-up and caches the token to disk.
    - First call: opens the browser for login.
    - Subsequent calls within the same session (cache still valid): silent, no browser needed.
    """
    cache = _load_cache()
    app = msal.PublicClientApplication(client_id=CLIENT_ID, authority=AUTHORITY, token_cache=cache)

    result = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(scopes=SCOPE, account=accounts[0])

    if not result:
        print("Opening browser for Power BI authentication. Please log in and return here when done.", flush=True)
        result = app.acquire_token_interactive(scopes=SCOPE)
        print("Authentication complete.", flush=True)

    _save_cache(cache)

    if "access_token" not in result:
        print(json.dumps({
            "error": result.get("error"),
            "description": result.get("error_description"),
        }), file=sys.stderr)
        sys.exit(1)
    return result["access_token"]


def api_get(path, token):
    resp = requests.get(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


def list_reports(workspace_id, token):
    data = api_get(f"/groups/{workspace_id}/reports", token)
    return [
        {"id": r["id"], "name": r["name"], "datasetId": r.get("datasetId", "")}
        for r in data.get("value", [])
    ]


def get_parameters(workspace_id, dataset_id, token):
    """Returns [{name, currentValue}] for each parameter. Empty list if dataset has none or is inaccessible."""
    if not dataset_id:
        return []
    try:
        data = api_get(f"/groups/{workspace_id}/datasets/{dataset_id}/parameters", token)
        return [
            {"name": p["name"], "currentValue": p.get("currentValue", "")}
            for p in data.get("value", [])
        ]
    except requests.HTTPError as e:
        if e.response.status_code in (403, 404):
            return []
        raise


def cmd_list_reports(args, token):
    reports = list_reports(args.workspace_id, token)
    print(json.dumps(reports, indent=2, ensure_ascii=False))


def cmd_get_parameters(args, token):
    params = get_parameters(args.workspace_id, args.dataset_id, token)
    print(json.dumps(params, indent=2, ensure_ascii=False))


def cmd_report_info(args, token):
    reports = list_reports(args.workspace_id, token)

    if args.all:
        results = []
        for r in reports:
            params = get_parameters(args.workspace_id, r["datasetId"], token)
            results.append({
                "name": r["name"],
                "datasetId": r["datasetId"],
                "parameters": params,
            })
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    # Single report lookup — exact match first, then partial
    query = args.report_name.lower()
    exact = [r for r in reports if r["name"].lower() == query]
    partial = [r for r in reports if query in r["name"].lower() or r["name"].lower() in query]
    matches = exact if exact else partial

    if not matches:
        print(json.dumps({
            "found": False,
            "searchedName": args.report_name,
            "workspaceReportNames": [r["name"] for r in reports],
        }, indent=2, ensure_ascii=False))
        return

    r = matches[0]
    params = get_parameters(args.workspace_id, r["datasetId"], token)
    print(json.dumps({
        "found": True,
        "searchedName": args.report_name,
        "exactName": r["name"],
        "datasetId": r["datasetId"],
        "parameters": params,
        "multipleMatches": len(matches) > 1,
        "allMatches": [m["name"] for m in matches] if len(matches) > 1 else None,
    }, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Power BI Service read-only query helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("list-reports", help="List all reports in a workspace")
    p1.add_argument("--workspace-id", required=True)

    p2 = sub.add_parser("get-parameters", help="Get parameter names for a specific dataset")
    p2.add_argument("--workspace-id", required=True)
    p2.add_argument("--dataset-id", required=True)

    p3 = sub.add_parser("report-info", help="Find report(s) and their parameter names")
    p3.add_argument("--workspace-id", required=True)
    p3.add_argument("--all", action="store_true", help="Fetch info for all reports in the workspace")
    p3.add_argument("--report-name", help="Search for a specific report by name")

    args = parser.parse_args()

    if args.command == "report-info" and not args.all and not args.report_name:
        print("Error: report-info requires --all or --report-name", file=sys.stderr)
        sys.exit(1)

    token = authenticate()

    if args.command == "list-reports":
        cmd_list_reports(args, token)
    elif args.command == "get-parameters":
        cmd_get_parameters(args, token)
    elif args.command == "report-info":
        cmd_report_info(args, token)


if __name__ == "__main__":
    main()
