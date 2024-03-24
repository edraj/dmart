from locust import HttpUser, between, task

SPACE_NAME = "applications"

class WebsitePublic(HttpUser):
    wait_time = between(1, 2)
    host = "http://0.0.0.0:8282"

    # Query subpath
    # @task
    # def query_subpath(self):
    #     request_data = {
    #         "space_name": SPACE_NAME,
    #         "type": "subpath",
    #         "subpath": "/offers",
    #         "retrieve_json_payload": True
    #     }
    #     res = self.client.post("/public/query", json=request_data)
    #     print("\n\n\n ressss from public: ", res)

    # Query search
    @task(10)
    def query_search(self):
        request_data = {
            "space_name": SPACE_NAME,
            "type": "search",
            "subpath": "/queries",
            "filter_schema_names": ["query"],
            "retrieve_json_payload": True
        }
        self.client.post("/public/query", json=request_data)


    # Saved Query
    # @task
    # def execute_saved_query(self):
    #     request_data = {
    #         "attributes": {
    #             "limit": 117,
    #             "offer_ids": "12254|12329|12321|12319|12345"
    #         },
    #         "resource_type": "content",
    #         "shortname": "atl_offers",
    #         "subpath": "/saved_queries"
    #     }
    #     self.client.post("/public/excute/query/products", json=request_data)


    # # retrieve entry
    # @task
    # def retrieve_entry(self):
    #     self.client.get("/managed/entry/content/applications/queries/order?retrieve_json_payload=true")


    # retrieve media
    # @task
    # def retrieve_payload(self):
    #     self.client.get("/public/payload/media/products/banners/banner2/en.png")



