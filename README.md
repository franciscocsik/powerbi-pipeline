# Power BI Migration Pipeline

A Python script that automates the migration of Power BI reports between workspaces (e.g. from `prod` to `dev`, or `dev` to `test`) and, optionally, the publishing of local `.pbix` files to any target workspace. After importing each report, it optionally updates the semantic model's connection parameters in the target workspace.

---

## What it does

For each report defined in `reports.json`, the pipeline:

1. Authenticates interactively with your Microsoft account (opens the browser)
2. Exports the `.pbix` file from the source workspace
3. Deletes the existing report and dataset in the target workspace (if any)
4. Imports the `.pbix` into the target workspace
5. If `parameters` are defined for the report, waits for the import to complete and updates the semantic model's connection parameters

---

## Requirements

```bash
pip install msal requests
```

---

## How to run

```bash
python main.py
```

A browser window will open asking you to log in with your Microsoft account. Once authenticated, the migration runs automatically for all reports listed in `reports.json`.

---

## Configuration

### `workspaces.json`

Maps each domain and environment combination to a Power BI workspace ID.

```json
{
  "commercial_ops": {
    "dev":  "<workspace-id>",
    "test": "<workspace-id>",
    "prod": "<workspace-id>"
  },
  "finance": {
    "dev":  "<workspace-id>",
    "test": "<workspace-id>"
  }
}
```

**How to find a workspace ID in Power BI:**

1. Go to [app.powerbi.com](https://app.powerbi.com)
2. Open the workspace you need
3. Look at the URL — it will look like:
   ```
   https://app.powerbi.com/groups/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/list
   ```
4. The UUID between `/groups/` and `/list` is the workspace ID

---

### `reports.json`

Defines which reports to migrate and, optionally, what connection parameters to set on the semantic model after migration.

You can define **multiple reports in the same run** — the pipeline processes them sequentially as a batch.

```json
[
  {
    "reportName": "Sales Dashboard",
    "domain": "commercial_ops",
    "sourceWorkspace": "prod",
    "targetWorkspace": "dev",
    "parameters": {
      "HTTPPath": "/sql/1.0/warehouses/abc123",
      "Server": "adb-1234567890.12.azuredatabricks.net",
      "DefaultCatalog": "hive_metastore",
      "Schema": "commercial_ops_prod"
    }
  },
  {
    "reportName": "HR Report",
    "domain": "hr",
    "sourceWorkspace": "prod",
    "targetWorkspace": "test"
  }
]
```

**Field reference:**

| Field | Description |
|---|---|
| `reportName` | Exact name of the report in the source workspace |
| `domain` | Domain key as defined in `workspaces.json` |
| `sourceWorkspace` | Environment to migrate from (`dev`, `test`, or `prod`) |
| `targetWorkspace` | Environment to migrate to (`dev`, `test`, or `prod`) |
| `parameters` | *(Optional)* Connection parameters to update on the semantic model after migration |

#### About the `parameters` block <a id="about-the-parameters-block"></a>

- The `parameters` block is **entirely optional**. If omitted (like the `HR Report` example above), the report is migrated as-is and no parameter update is attempted.
- You only need to include the parameters you want to update. Any parameters present in the semantic model that are **not listed here will remain unchanged** — they keep whatever values they had in the source workspace after migration.
- To skip a specific parameter, you can either remove it from the block or set it to `null` — both behave identically.
- The parameter names must match **exactly** the names defined in the `.pbix` file (see warning below).

> [!WARNING]
> **Parameter names can vary between reports even when they represent the same concept.**
> For example, some semantic models use `DefaultCatalog` while others use `Catalog` — both refer to the same database catalog but are defined differently in each `.pbix` file. Using the wrong name will cause a 404 error when the pipeline tries to update the parameters.
>
> Before running the migration, verify the exact parameter names for each report by opening it in **Power BI Desktop → Transform Data → Manage Parameters**. Use those exact names in `reports.json`.

---

## Uploading local `.pbix` files

In addition to migrating reports between workspaces, the pipeline can publish `.pbix` files sitting in the local `upload/` folder to any target workspace. This runs **after** the workspace-to-workspace migration and is entirely optional — if `upload/reports.json` does not exist, this step is skipped.

### How it works

For each entry in `upload/reports.json`, the pipeline:

1. Reads the `.pbix` file from the `upload/` folder
2. Derives the report name from the file name (without the `.pbix` extension)
3. Deletes the existing report and dataset in the target workspace (if any)
4. Imports the `.pbix` into the target workspace
5. If `parameters` are defined, waits for the import to complete and updates the semantic model's connection parameters

The `.pbix` file is **not deleted** from `upload/` after publishing, so the same batch can be re-run without recopying files.

### `upload/reports.json`

```json
[
  {
    "file": "Sales Dashboard.pbix",
    "domain": "commercial_ops",
    "targetWorkspace": "dev",
    "parameters": {
      "HTTPPath": "/sql/1.0/warehouses/abc123",
      "Server": "adb-1234567890.12.azuredatabricks.net"
    }
  },
  {
    "file": "HR Report.pbix",
    "domain": "hr",
    "targetWorkspace": "test"
  }
]
```

**Field reference:**

| Field | Description |
|---|---|
| `file` | Exact name of the `.pbix` file inside `upload/`. The report name in Power BI is derived from this by removing the `.pbix` extension |
| `domain` | Domain key as defined in `workspaces.json` |
| `targetWorkspace` | Environment to publish to (`dev`, `test`, `prod`, `sandbox`, …) |
| `parameters` | *(Optional)* Connection parameters to update on the semantic model after upload. Same rules as the migration flow — see the [`parameters` block](#about-the-parameters-block) section above |

There is no `sourceWorkspace` field because the `.pbix` is read from disk.

---

## Project structure

```
├── main.py               # Entry point — orchestrates the full migration flow
├── utils.py              # Power BI API helper functions
├── reports.json          # List of reports to migrate with their configuration
├── workspaces.json       # Workspace ID mapping by domain and environment
└── upload/
    ├── reports.json      # (Optional) List of local .pbix files to publish
    └── *.pbix            # Local report files ready to publish
```
