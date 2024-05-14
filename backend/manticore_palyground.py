import asyncio
import json
from pprint import pprint
import manticoresearch
from db.manticore_db import ManticoreDB
from models.core import EntityDTO
from models.enums import ResourceType
from repositories.manticore_repo import ManticoreRepo


def main():
    config = manticoresearch.Configuration(host="http://127.0.0.1:9308")
    client = manticoresearch.ApiClient(config)
    indexApi = manticoresearch.IndexApi(client)
    searchApi = manticoresearch.SearchApi(client)
    utilsApi = manticoresearch.UtilsApi(client)

    # Create table
    utilsApi.sql(
        "CREATE TABLE forum(title text, content text, author_id int, forum_id int, post_date timestamp)"
    )

    # Insert
    indexApi.insert(
        {
            "index": "products",
            "doc": {"title": "Crossbody Bag with Tassel", "price": 19.85},
        }
    )
    indexApi.insert(
        {"index": "products", "doc": {"title": "microfiber sheet set", "price": 19.99}}
    )
    indexApi.insert(
        {"index": "products", "doc": {"title": "Pet Hair Remover Glove", "price": 7.99}}
    )

    # res = utilsApi.sql('SELECT current_user();')
    # pprint(res)
    res = utilsApi.sql("SHOW TABLES")
    pprint(res)


async def main2():
    mdb = ManticoreDB()
    dto = EntityDTO(
        space_name="management",
        branch_name="master",
        subpath="workflows",
        shortname="channel",
        resource_type=ResourceType.content
    )
    res = await mdb.find(dto)
    # mr = ManticoreRepo()
    # await mdb.flush_all()
    # res = await mdb.find_by_id('spaces')
    # res = mdb.mc_command("describe management__master__meta")
    # index_schema = res['data']
    # index_fields = {field['Field'] for field in index_schema}
    # res = await mdb.create_index("test_index", {
    #     "title": "string",
    #     "json_attr": "json"
    # })
    pprint(res)
    # res = mdb.indexApi.insert({
    #     "index": "test_index",
    #     "doc": {
    #         'title': 'Example Document',
    #         'json_attr': {'item1': 'dwqd', 'item2':'sqdqw', 'item3': 'fwegwe'}  # This is the list attribute
    #     }
    # })
    # pprint(res)
    # res = mdb.indexApi.insert({ # This is the list attribute
    #     "index": "test_index",
    #     "doc": {
    #         'title': 'Example Document',
    #         'json_attr': ['item1', 'item2', 'item3']
    #     }
    # })
    # res = mdb.mc_command("SELECT * FROM test_index where id = 8217226484037714144")
    # pprint(res)
    # res = mdb.indexApi.insert(
    #     {
    #         "index": "management__master__meta",
    #         "doc": {
    #             "uuid": "d5e03f10-dab0-4113-b9b8-4b85e60db2e6",
    #             "shortname": "view_ticket",
    #             "is_active": True,
    #             "displayname": {"en": "view_ticket", "ar": "view_ticket"},
    #             "tags": [],
    #             "created_at": 1675326093.91245,
    #             "updated_at": 1675326093.912459,
    #             "owner_shortname": "dmart",
    #             "query_policies": [
    #                 "management::permission:true:dmart",
    #                 "management::permission:true",
    #                 "management:__all_subpaths__:permission:true",
    #                 "management:permissions:permission:true:dmart",
    #                 "management:permissions:permission:true",
    #             ],
    #             "subpath": "permissions",
    #             "resource_type": "permission",
    #             "payload_string": "",
    #             "document_id": "management:master:meta:permissions/view_ticket",
    #         },
    #     }
    # )
    # pprint(res)
    # print(type(res))
    # pprint(await mdb.set_key('oneee', 'threeew222'))
    # pprint(await mdb.find_key('oneee'))

    # pprint(await mdb.list_indexes())
    # await mdb.create_application_indexes()
    # pprint(await mdb.list_indexes())


if __name__ == "__main__":
    # main()
    # print("===== END =====")
    asyncio.run(main2())
