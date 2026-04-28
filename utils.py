import os
import re
import time
import requests
from urllib.parse import quote_plus
from urllib.parse import quote

API_BASE = "https://api.powerbi.com/v1.0/myorg"

#deprecated function
def sanitize_name(name):
    #limpia algunos caracteres de un string
    return re.sub(r'[&()#\'"{}<>?*:/\\|]', '_', name)

def export_report(report_name, workspace_id, access_token):
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)

    response.raise_for_status()
    reports = response.json().get("value", [])
    report = next((r for r in reports if r["name"] == report_name), None)

    if not report:
        print(f"⚠️ Couldn't find report '{report_name}' on {workspace_id}")
        return None

    export_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report['id']}/Export"
    r = requests.get(export_url, headers=headers)
    r.raise_for_status()

    file_path = f"{report_name}.pbix"
    with open(file_path, "wb") as f:
        f.write(r.content)

    print(f"Exporting '{report_name}' → {file_path}")
    return file_path

def import_report(file_path, report_name, workspace_id, access_token):
    encoded_report_name = quote(report_name, safe='').replace('.', '%2E')
    url = (
        f"{API_BASE}/groups/{workspace_id}/imports"
        f"?datasetDisplayName={encoded_report_name}&nameConflict=CreateOrOverwrite"
    )
    headers = {"Authorization": f"Bearer {access_token}"}

    with open(file_path, "rb") as pbix_file:
        response = requests.post(url, headers=headers, files={"file": pbix_file})

    response.raise_for_status()
    import_id = response.json()["id"]
    print(f"Importing '{report_name}' to workspace {workspace_id} (import ID: {import_id})")
    return import_id

def wait_for_import(import_id, workspace_id, access_token, timeout_seconds=120, poll_interval=3):
    url = f"{API_BASE}/groups/{workspace_id}/imports/{import_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    elapsed = 0

    while elapsed < timeout_seconds:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        body = response.json()
        state = body.get("importState")

        if state == "Succeeded":
            datasets = body.get("datasets", [])
            if not datasets:
                raise RuntimeError(f"Import {import_id} succeeded but returned no datasets.")
            dataset_id = datasets[0]["id"]
            print(f"Import succeeded. Dataset ID: {dataset_id}")
            return dataset_id

        if state in ("Failed", "TimedOut"):
            raise RuntimeError(f"Import {import_id} ended with state '{state}'. Response: {body}")

        print(f"Import state: '{state}'. Waiting {poll_interval}s...")
        time.sleep(poll_interval)
        elapsed += poll_interval

    raise RuntimeError(f"Import {import_id} did not complete within {timeout_seconds} seconds.")

def update_semantic_model_parameters(dataset_id, workspace_id, parameters, access_token):
    update_details = [
        {"name": name, "newValue": value}
        for name, value in parameters.items()
        if value is not None and value != ""
    ]

    if not update_details:
        print(f"No parameters to update for dataset {dataset_id}. Skipping.")
        return

    url = f"{API_BASE}/groups/{workspace_id}/datasets/{dataset_id}/Default.UpdateParameters"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(url, headers=headers, json={"updateDetails": update_details})
    response.raise_for_status()
    print(f"Updated parameters {[d['name'] for d in update_details]} on dataset {dataset_id}")

# def import_report(file_path, report_name, workspace_id, access_token):
#     base_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports"
#     headers = {
#         "Authorization": f"Bearer {access_token}"
#     }
#     params = {
#         "datasetDisplayName": report_name,
#         "nameConflict": "CreateOrOverwrite"
#     }
#     with open(file_path, "rb") as pbix_file:
#         files = {"file": pbix_file}
#         print(files)
#         response = requests.post(base_url, headers=headers, params=params, files=files)
#         print(response)

def deleteObjectsWithName(objectIds, objectType, workspace_id, access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    for id in objectIds:
        print(f"{objectType} deleted; ID: {id}")
        del_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/{objectType}/{id}"
        del_resp = requests.delete(del_url, headers=headers)
        del_resp.raise_for_status()
        # print(f"✅ {objectType} '{objectIds}' eliminado antes de importar")

def getObjectsWithName(name, type, workspace_id, access_token):
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/{type}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    x = []
    for object in response.json().get("value", []):
        if object["name"] == name:
            id = object["id"]
            x.append(id)
    return x

# def rename_report(report_id, new_name, workspace_id, access_token):
#     url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}"
#     headers = {
#         "Authorization": f"Bearer {access_token}",
#         "Content-Type": "application/json"
#     }
#     print(f"a ver si funciona: {report_id}")
#     body = {"name": new_name}
#     response = requests.patch(url, headers=headers, json=body)
#     print("Detalles:", response.text)
#     if response.status_code not in (200, 204):
#         print(f"⚠️ No se pudo renombrar el reporte a '{new_name}' (status {response.status_code})")
#     else:
#         print(f"✏️ Renombrado a '{new_name}'")

        