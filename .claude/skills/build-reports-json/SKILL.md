---
name: build-reports-json
description: Interactively builds reports.json for the Power BI migration pipeline. Guides through collecting report names, domains, and workspaces, then queries Power BI Service to get exact report names and semantic model parameter names, and generates a validated reports.json file ready for main.py.
disable-model-invocation: true
allowed-tools: Bash(python "${CLAUDE_SKILL_DIR}/scripts/pbi_query.py" *) Read(workspaces.json) Read(reports.json) Read("${CLAUDE_SKILL_DIR}/omit-params.json") Read("${CLAUDE_SKILL_DIR}/domain-schema-defaults.json") Write(reports.json)
---

# Build reports.json

> **Non-negotiable rule: never infer.** Do not guess, assume, or autocomplete report names, parameter names, parameter values, workspace IDs, or connection strings. If anything is unclear or missing, stop and ask the user. This rule applies at every phase.

---

## Phase 1 — Collect inputs from the user

Ask the user for all of the following in a single message. Do not proceed until every item is answered.

**1. Report names**
Ask for the full list of reports to migrate. Accept them exactly as the user writes them (they may include characters that were stripped in the workspace — that is handled in Phase 3).

Recommend the **structured format** where domain headers group the reports — this pre-answers input 2 and avoids a separate step:

```
customer_relations
C4A - Report A
C4A - Report B
C4A - Report C

distribution
AMI Outage Summary
MN Disconnects Dashboard
```

If the user provides a flat list with no domain headers, proceed to input 2 to assign domains.

**2. Domain(s)**
If domains were already specified in input 1 via structured format, extract the mapping from there — skip this question.

If input 1 was a flat list, read `workspaces.json`, show the available domain keys, and ask the user to assign domains. Accept any of these formats:

- *Structured (recommended):* domain header followed by the reports that belong to it (same as input 1 structured format)
- *Natural language:* e.g. "the first 5 are `customer_relations`, the next 3 are `distribution`, the rest are `transmission`" — interpret positionally against the list from input 1
- *Per-report:* explicit assignment for each report

If the interpretation of any assignment is ambiguous, stop and ask for clarification. Never assume a domain for a report.

**3. Source workspace**
Which environment to pull from: `dev`, `test`, or `prod`.

**4. Target workspace**
Which environment to push to: `dev`, `test`, or `prod`.

**5. Databricks connection strings**
Ask: "Should we use the default prd-us-east-2 Databricks connection strings?

- `HTTPPath`: `/sql/1.0/warehouses/22c10bda745e9df9`
- `Server`: `dbc-1b8ccdbb-871b.cloud.databricks.com`

If not, provide the `HTTPPath` and `Server` values you want to use."

If the user confirms the defaults, store those values. If not, wait for the user to provide them before continuing.

**6. Catalog value**
Ask: "The default value for `DefaultCatalog` / `Catalog` is `prd_mart_zone`. Is that correct, or do you want to use a different value?"

If the user confirms, use `prd_mart_zone`. If not, wait for the user to provide the value before continuing.

**7. Schema value**
Read `${CLAUDE_SKILL_DIR}/domain-schema-defaults.json` to get the default schema value for each domain.

For each domain in the user's list:
- If the domain **has a mapping** in the file: show the default and ask for confirmation — e.g. "For `customer_relations` the default schema is `customer_enterprise`. Is that correct?"
- If the domain **has no mapping**: ask the user explicitly — "Domain `<domain>` has no default schema defined. What value should Schema parameters be set to for reports in this domain?"

Never assume or infer a schema value. Store the confirmed value per domain.

(Applies to all parameters whose name starts with `Schema` — `Schema`, `Schema1`, `Schema2`, `SchemaAwr`, `SchemaAwb`, etc.)

**8. Write mode**
Ask: "Should this overwrite `reports.json` completely, or add these reports to the existing file (incremental mode)?"

Store the answer — it determines behavior in Phase 5.

---

## Phase 2 — Look up workspace IDs and query Power BI Service

**2.1 — Get workspace IDs**

Read `workspaces.json`. For each unique domain in the user's list, get the workspace ID for the source environment:

```
workspace_id = workspaces[domain][sourceWorkspace]
```

**2.2 — Query Power BI Service**

For each unique source workspace ID, run:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/pbi_query.py" report-info --workspace-id <id> --all
```

**Authentication:**

- A browser window opens automatically for login. The script prints "Opening browser for Power BI authentication..." before it opens and "Authentication complete." when done — both visible in the output.
- **The token is cached to disk** (`~/.pbi_tool_cache.json`). If reports span multiple domains, only the first call opens the browser — subsequent calls reuse the cached token silently.

The script returns a JSON array where each object has:
- `name`: exact report name as it exists in Power BI Service
- `datasetId`: the associated semantic model ID
- `parameters`: list of `{name, currentValue}` objects for each semantic model parameter

If the script fails for any reason (auth error, network error, unexpected output), report the error message to the user and stop. Do not attempt to build the JSON without this data.

---

## Phase 3 — Match reports and assign parameter values

### 3.1 — Match each report name

For each report name the user provided, find its exact name in the API response for the corresponding workspace.

- **Exact match** (case-insensitive): proceed automatically.
- **No match found**: stop and tell the user. Show the full list of report names available in that workspace so the user can identify the correct one. Do not guess.
- **Multiple partial matches**: show all candidates to the user and ask them to confirm which is the right one.

Build a mapping: user-provided name → exact workspace name.

### 3.2 — Assign parameter values

Read `${CLAUDE_SKILL_DIR}/omit-params.json` to get the current list of parameter names to omit.

The API response for each report now includes both `name` and `currentValue` for every parameter. Apply the following rules. Only include a parameter in a report's entry if that specific report has it in its `parameters` list.

| Parameter name(s) | Action |
|---|---|
| `HTTPPath` | Use value from Phase 1 input 5 |
| `Server` | Use value from Phase 1 input 5 |
| `DefaultCatalog` or `Catalog` | Use value from Phase 1 input 6 (same value for both names, all reports) |
| Any name starting with `Schema` (e.g. `Schema`, `Schema1`, `Schema2`, `SchemaAwr`, `SchemaAwb`, …) | Use the schema value for that report's domain (Phase 1 input 7) |
| Any name listed in `omit-params.json` | **Omit** — do not add to the JSON for any report |
| Any other name not listed above | Use the `currentValue` from the API response. If `currentValue` is empty, **do not include the parameter in the JSON** |

If a report has no `parameters` in the API response, flag it to the user: "Report X has no parameters — is that expected?" Wait for confirmation before continuing.

Track two lists for the post-save summary:
- Parameters kept from source (any other name with a non-empty `currentValue`)
- Parameters excluded because `currentValue` was empty in source

---

## Phase 4 — Build, diff, and validate the JSON

### 4.1 — Build

Construct the new entries array. Each entry:

```json
{
  "reportName": "<exact name from workspace>",
  "domain": "<domain from user>",
  "sourceWorkspace": "<env from user>",
  "targetWorkspace": "<env from user>",
  "parameters": {
    "HTTPPath": "<value>",
    "Server": "<value>",
    "<paramName>": "<value>"
  }
}
```

Only include parameters in the `parameters` object if that specific report has them in its `parameters` list from the API response. Do not add parameters to a report that didn't have them in the API response.

### 4.2 — Diff against existing reports.json

Read the current `reports.json` (if it exists) and compute the diff between the existing content and the new entries:

- **New reports** (in new list, not in existing file): list them as additions
- **Removed reports** (in existing file, not in new list): list them — only relevant in overwrite mode
- **Modified reports** (same name, different parameters or fields): list the specific fields that changed

Present the diff to the user before the validation summary. If there is no existing file, skip this step.

### 4.3 — Validation

Flag any of the following to the user before saving:

- `sourceWorkspace` and `targetWorkspace` are the same value (likely a mistake — confirm with user)
- A report could not be matched to the workspace (was not found)
- A report has an empty `parameters` object when others don't (may be intentional — confirm)
- Any parameter value is empty or `null` in the generated JSON (should not happen — parameters with empty `currentValue` are excluded entirely, not written as empty)
- `HTTPPath` does not start with `/sql/1.0/warehouses/`
- `Server` does not end with `.cloud.databricks.com` or `.azuredatabricks.net`
- The same report name appears more than once in the user's input list

Show the complete generated JSON and ask: "Does this look correct? Should I save it to `reports.json`?"

---

## Phase 5 — Save

Only write the file after the user explicitly confirms.

**Overwrite mode**: write the new entries array directly to `reports.json`.

**Incremental mode**:
1. Read the existing `reports.json`.
2. For each report in the new batch, check if a report with the same `reportName` already exists in the file.
   - If it does **not exist**: add it.
   - If it **already exists**: ask the user: "Report `<name>` already exists in reports.json. Replace it with the new entry, or keep the existing one?"
3. Write the merged array to `reports.json`.

After saving, show the following:

**1. Confirmation:** "File saved."

**2. Kept-from-source summary** — if any parameters were carried over from the source workspace (the "any other name" rule in Phase 3.2), display a table:

```
Parameters kept with value from source workspace — verify before running main.py:

  <Report Name>   →  <paramName>:  "<value>"
  <Report Name>   →  <paramName>:  "<value>"
  ...
```

To locate each one in the JSON file, search (Ctrl+F) for the parameter name — e.g. `"ToDate"`.

**3. Excluded parameters summary** — if any parameters were not included because `currentValue` was empty in the source workspace, list them:

```
Parameters not included (empty in source workspace):

  <Report Name>   →  <paramName>
```

If neither summary applies, tell the user: "All parameters were resolved — no manual edits needed."
