import time
from locust import HttpUser, between, task
import os
from glob import glob
from shutil import rmtree
import subprocess

SPACE_NAME = "applications"
BASE_PATH = os.path.dirname(os.getcwd())
LOGIN_CREDS="../login_creds.sh"
pipe = subprocess.Popen(['/bin/bash', '-c', f"grep 'export SUPERMAN' {LOGIN_CREDS} | cut -f2 -d \"'\" | jq -r .password"], stdout=subprocess.PIPE)
if not os.path.exists(LOGIN_CREDS) or not os.path.isfile(LOGIN_CREDS) or not pipe or not pipe.stdout:
    print("Failed to get the dmart password needed for testing")


SHORTNAME = "dmart"
PASSWORD = pipe.stdout.read().decode().strip() if pipe.stdout else ""


class WebsiteUser(HttpUser):
    wait_time = between(1, 2)
    host = "http://0.0.0.0:8282"
    headers = {"Content-Type": "application/json"}
    stamp = str(time.time()).replace(".", "")[-7:]
    
    def on_start(self):
        res = self.client.post("/user/login", json={"shortname": SHORTNAME, "password": PASSWORD}, headers=self.headers)
        self.client.cookies.set("auth_token", res.json()["records"][0]["attributes"]["access_token"])
        # self.headers["Authorization"] = "Bearer " + res.json()["records"][0]["attributes"]["access_token"]

    @task
    def user_get_profile(self):
        self.client.get("/user/profile", headers=self.headers)


    @task
    def create_folder_resource(self):
        request_data = {
            "space_name": SPACE_NAME,
            "request_type": "create",
            "records": [
                {
                    "resource_type": "folder",
                    "subpath": "/content",
                    "shortname": "auto",
                    "attributes": {
                        "tags": ["one", "two"],
                        "displayname": {"en":"This is a nice one"},
                        "description": {"en": "Further description could help"},
                    },
                }
            ],
        }
        res = self.client.post("/managed/request", json=request_data, headers=self.headers)
        if res.status_code != 200:
            print(f"\n\n FAILED REQUEST: {res.json()}")
    
    
    @task
    def create_content_resource(self):
        request_data = {
            "space_name": SPACE_NAME,
            "request_type": "create",
            "records": [
                {
                    "resource_type": "content",
                    "subpath": "content",
                    "shortname": "auto",
                    "attributes": {
                        "is_active": True,
                        "payload": {
                            "content_type": "json",
                            "body": {
                                "provider": {
                                    "kyo_id": "2",
                                    "kyo_priority": 0,
                                    "type": "BTL"
                                },
                                "cbs_name": "Mock_Offer_2",
                                "cbs_id": "2",
                                "crm_id": "2",
                                "toms_id": "1323152",
                                "title": {
                                    "en": "Mock Offer 2",
                                    "ar": "\u0639\u0631\u0636 \u062a\u062c\u0631\u064a\u0628\u064a 2",
                                    "kd": "\u0639\u0631\u0636 \u062a\u062c\u0631\u064a\u0628\u064a 2"
                                },
                                "desc": {
                                    "en": "Mock Offer 2",
                                    "ar": "\u0639\u0631\u0636 \u062a\u062c\u0631\u064a\u0628\u064a 2",
                                    "kd": "\u0639\u0631\u0636 \u062a\u062c\u0631\u064a\u0628\u064a 2"
                                },
                                "specs": {
                                    "price": 2000001,
                                    "validity": 31,
                                    "can_unsubscribe": "No",
                                    "special_offer": "Yes"
                                },
                                "services": [
                                    {
                                        "type": "data",
                                        "data": 100000,
                                        "ul": "Yes",
                                        "restricted": "No"
                                    },
                                    {
                                        "type": "voice",
                                        "onnet": 150,
                                        "offnet": 0,
                                        "crossnet": 100,
                                        "onnet_off_peak": 0
                                    }
                                ],
                                "hide_from_listing": "No",
                                "offer_type_localization": {
                                    "en": "Mock Offer 2",
                                    "ar": "\u0639\u0631\u0636 \u062a\u062c\u0631\u064a\u0628\u064a 2",
                                    "kd": "\u0639\u0631\u0636 \u062a\u062c\u0631\u064a\u0628\u064a 2"
                                }
                            }
                        }
                    }
                }
            ],
        }
        res = self.client.post("/managed/request", json=request_data, headers=self.headers)
        if res.status_code != 200:
            print(f"\n\n FAILED create_content_resource: {res.json()}")


    @task
    def create_schema_resource(self):
        upload_file_schema = "../sample/test/createschema.json"
        upload_file_payload_schema = "../sample/test/schema.json"
        with open(upload_file_schema, "rb") as request_record, open(upload_file_payload_schema, "rb") as payload_file:
            # print(f"\n\n\n request_record: {request_record.read()} \n\n")
            files = {
                "request_record": request_record,
                "payload_file": payload_file
            }
            res = self.client.post(
                "/managed/resource_with_payload", 
                data={"space_name": SPACE_NAME}, 
                files=files
            )
            if res.status_code != 200:
                print(f"\n\n FAILED create_schema_resource: {res.json()}")

    @task
    def delete_resource(self):
        stamp = str(time.time()).replace(".", "")[-7:]
        headers = {"Content-Type": "application/json"}
        request_data = {
            "space_name": SPACE_NAME,
            "request_type": "create",
            "records": [
                {
                    "resource_type": "content",
                    "subpath": "content",
                    "shortname": f"{stamp}",
                    "attributes": {
                        "payload": {
                            "body": "this content created from curl request for testing",
                            "content_type": "text",
                        },
                        "tags": ["one", "two"],
                        "displayname": {"en":"This is a nice one"},
                        "description": {"en": "Further description could help"},
                    }
                }
            ],
        }
        self.client.post("/managed/request", json=request_data, headers=self.headers)

        endpoint = "/managed/request"
        request_data = {
            "space_name": SPACE_NAME,
            "request_type": "delete",
            "records": [
                {
                    "resource_type": "content",
                    "subpath": "/content",
                    "shortname": f"{stamp}",
                    "attributes": {},
                }
            ],
        }

        res = self.client.post(endpoint, json=request_data, headers=headers)
        if res.status_code != 200:
            print(f"\n\n FAILED delete_resource: {res.json()}")

    
    # retrieve entry
    # @task
    # def retrieve_entry(self):
    #     self.client.get("/managed/entry/schema/test/schema/test_schema?retrieve_json_payload=true&retrieve_attachments=true", headers=self.headers)

    
    # health API
    # @task
    # def health_check(self):
    #     self.client.get("/managed/health/management", headers=self.headers)

    # retrieve entry
    @task
    def retrieve_entry(self):
        self.client.get("/managed/entry/content/applications/queries/order?retrieve_json_payload=true")

    @task(3)
    def query_subpath(self):
        request_data = {
            "space_name": SPACE_NAME,
            "type": "subpath",
            "subpath": "/offers",
            "retrieve_json_payload": True
        }
        self.client.post("/managed/query", json=request_data, headers=self.headers)


    def on_stop(self):
        # cleaning

        for item in glob(f"{BASE_PATH}/spaces/{SPACE_NAME}/*"):
            if item.__contains__("myposts_"):
                rmtree(item)

        for item in glob(f"{BASE_PATH}/spaces/{SPACE_NAME}/*"):
            if item.__contains__("myfolder_"):
                rmtree(item)

        for item in glob(f"{BASE_PATH}/spaces/{SPACE_NAME}/content/*"):
            if item.__contains__("myposts_"):
                rmtree(item)

    
