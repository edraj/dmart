import strawberry
from models.schema import QueryGQL, RecordGQL
from utils.repository import subpath_query

@strawberry.type
class Query:
    @strawberry.field
    async def subpath_query(self, search_query: QueryGQL) -> list[RecordGQL]:
        records, total = await subpath_query(search_query, "dmart")

        return records