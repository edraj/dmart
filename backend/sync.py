import argparse
import hashlib
import json
import requests

from models.enums import RequestType
from utils.settings import settings


local_username = "dmart"
local_password = "Test1234"


headers = {
    "accept": "application/json, text/plain, */*",
}
target_headers = {
    **headers,
}
local_headers = {
     **headers,
}

body = {
    "filter_shortnames": [],
    "type": "search",
    "exact_subpath": True,
    "limit": 100,
    "offset": 0,
    "search": "",
    "retrieve_json_payload": True,
}


def login(username, password, target):
    body = {
        "shortname": username,
        "password": password,
    }

    response = requests.post(f"{target}/user/login", headers=headers, json=body,)

    if response.ok:
        return response.json()["records"][0]["attributes"]["access_token"]
    else:
        print(f"Error: {response.status_code}, {response.text}")


def hash_records(local_records, target_records):
    hashed_local_records = {}
    hashed_target_records = {}
    for local_record in local_records:
        sha1 = hashlib.sha1()
        r = {
            "shortname": local_record["shortname"],
            "displayname": local_record.get("attributes", {}).get("displayname", {}),
            "description": local_record.get("attributes", {}).get("description", {}),
        }
        if local_record.get("attributes", {}).get("payload", {}):
            r["payload"] = local_record.get("attributes", {}).get("payload", {}).get("checksum", {})
        else:
            r["payload"] = None
        sha1.update(json.dumps(r).encode())
        checksum = sha1.hexdigest()
        hashed_local_records[local_record["shortname"]] = checksum

    for target_record in target_records:
        sha1 = hashlib.sha1()
        r = {
            "shortname": target_record["shortname"],
            "displayname": target_record.get("attributes", {}).get("displayname", {}),
            "description": target_record.get("attributes", {}).get("description", {}),
        }
        if target_record.get("attributes", {}).get("payload", {}):
            r["payload"] = target_record.get("attributes", {}).get("payload", {}).get("checksum", {})
        else:
            r["payload"] = None
        sha1.update(json.dumps(r).encode())
        checksum = sha1.hexdigest()
        hashed_target_records[target_record["shortname"]] = checksum

    return hashed_local_records, hashed_target_records


local_records = []
target_records = []
def fetch_locators(space, subpath, target):
    global local_records
    global target_records

    body["space_name"] = space
    body["subpath"] = subpath

    response_target = requests.post(f"{target}/managed/query", headers=target_headers, json=body,)
    response_local = requests.post(f"http://{settings.listening_host}:{settings.listening_port}/managed/query", headers=local_headers, json=body,)

    if response_target.ok:
        target_records = response_target.json()["records"]
        print('# target records:', len(target_records))
    else:
        print(f"Error: {response_target.status_code}, {response_target.text}")

    if response_local.ok:
        local_records = response_local.json()["records"]
        print('# local records:', len(local_records))
    else:
        print(f"Error: {response_local.status_code}, {response_local.text}")

    return local_records, target_records


def get_diff(hashed_local_records, hashed_target_records):
    added_records = {k: v for k, v in hashed_local_records.items() if k not in hashed_target_records}
    removed_records = {k: v for k, v in hashed_target_records.items() if k not in hashed_local_records}
    different_records = {k: v for k, v in hashed_local_records.items() if k in hashed_target_records and hashed_target_records[k] != v}

    print(f"Added records: {added_records}")
    print(f"Removed records: {removed_records}")
    print(f"Different records: {different_records}")
    return added_records, removed_records, different_records


def apply_changes(space, target, added_records, removed_records, different_records):
    added_records_shortnames = [record for record in local_records if record["shortname"] in added_records]
    removed_records_shortnames = [record for record in target_records if record["shortname"] in removed_records]
    different_records_shortnames = [record for record in local_records if record["shortname"] in different_records]

    print(f"Added records shortnames: {added_records_shortnames}")
    print(f"Removed records shortnames: {removed_records_shortnames}")
    print(f"Different records shortnames: {different_records_shortnames}")

    request_data = {
        "space_name": space,
        "request_type": RequestType.create,
        "records": added_records_shortnames,
    }
    response = requests.post(f"{target}/managed/request", headers=target_headers, json=request_data,)
    if response.ok:
        print('records:', response.json())
    else:
        print(f"Error: {response.status_code}, {response.text}")

    request_data = {
        "space_name": space,
        "request_type": RequestType.delete,
        "records": removed_records_shortnames,
    }
    response = requests.post(f"{target}/managed/request", headers=target_headers, json=request_data,)
    if response.ok:
        print('records:', response.json())
    else:
        print(f"Error: {response.status_code}, {response.text}")

    request_data = {
        "space_name": space,
        "request_type": RequestType.update,
        "records": different_records_shortnames,
    }
    response = requests.post(f"{target}/managed/request", headers=target_headers, json=request_data,)
    if response.ok:
        print('records:', response.json())
    else:
        print(f"Error: {response.status_code}, {response.text}")


def main():
    parser = argparse.ArgumentParser(description="Process some arguments.")
    parser.add_argument('-u', required=True, help='The username argument')
    parser.add_argument('-p', required=True, help='The password argument')
    parser.add_argument('-sp', required=True, help='The space argument')
    parser.add_argument('-su', required=True, help='The subpath argument')
    parser.add_argument('-t', required=True, help='The target argument')
    parser.add_argument('-l', required=False, help='The limit argument')
    parser.add_argument('-o', required=False, help='The offset argument')

    args = parser.parse_args()

    print(f">Space: {args.sp}")
    print(f">Subpath: {args.su}")
    print(f">Target: {args.t}")
    print(f">Username: {args.u}")

    if args.l:
        body["limit"] = args.l
    if args.o:
        body["offset"] = args.o

    local_token = login(local_username, local_password, f"http://{settings.listening_host}:{settings.listening_port}")
    local_headers["Authorization"] = f"Bearer {local_token}"

    target_token = login(args.u, args.p, args.t)
    target_headers["Authorization"] = f"Bearer {target_token}"

    local_records, target_records = fetch_locators(args.sp, args.su, args.t)
    hashed_local_records, hashed_target_records = hash_records(local_records, target_records)
    added_records, removed_records, different_records = get_diff(hashed_local_records, hashed_target_records)
    apply_changes(args.sp, args.t, added_records, removed_records, different_records)



if __name__ == "__main__":
    main()