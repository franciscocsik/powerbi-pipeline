import os
import re
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

    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/imports?datasetDisplayName={encoded_report_name}&nameConflict=CreateOrOverwrite"
    print(url)
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    with open(file_path, "rb") as pbix_file:
        files = {"file": pbix_file}
        print(files)
        response = requests.post(url, headers=headers, files=files)
        print(response)

    response.raise_for_status()
    print(f"Importing '{report_name}' to {workspace_id}")

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

        