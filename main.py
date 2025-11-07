from msal import PublicClientApplication
import requests
import json
from utils import export_report, import_report, sanitize_name, getObjectsWithName, deleteObjectsWithName
import time

# Datos de tu tenant y tu cuenta
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46" # ID de la app pública oficial de Microsoft
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]

# Inicializamos la app MSAL
app = PublicClientApplication(client_id=CLIENT_ID, authority=AUTHORITY)

# Pedimos el token (te abre una ventana del navegador para loguearte)
result = app.acquire_token_interactive(scopes=SCOPE)
access_token = ''

if "access_token" in result:
    access_token = result['access_token']
    headers = {"Authorization": f"Bearer {access_token}"}
    # Ejemplo: obtener todos los reportes del workspace de DEV
    dev_workspace_id = "da52d16d-eda1-4e98-b296-3d59e34c0d85"
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{dev_workspace_id}/reports"
    resp = requests.get(url, headers=headers)
    reports = resp.json()

    # print(json.dumps(reports, indent=2))
else:
    print(result.get("error"))
    print(result.get("error_description"))

with open("reports.json", "r") as f:
    reports = json.load(f)

with open("workspaces.json", "r") as f:
    workspaces = json.load(f)

for report in reports:
    report_name = report["reportName"]
    source_env = report["sourceWorkspace"]
    target_env = report["targetWorkspace"]
    domain = report["domain"]

    source_workspace_id = workspaces[domain][source_env]
    target_workspace_id = workspaces[domain][target_env]

    print(f"Migrating '{report_name}' from '{source_env}' to '{target_env}'")

    file_path = export_report(report_name, source_workspace_id, access_token)

    oldReports = getObjectsWithName(report_name, 'reports', target_workspace_id, access_token)
    oldDatasets = getObjectsWithName(report_name, 'datasets', target_workspace_id, access_token)

    deleteObjectsWithName(oldReports, 'reports', target_workspace_id, access_token)
    deleteObjectsWithName(oldDatasets, 'datasets', target_workspace_id, access_token)

    import_report(file_path, report_name, target_workspace_id, access_token)

