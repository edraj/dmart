from typing import Any
from models.api import Query
from models.core import EntityDTO, Meta, Record
from repositories.base_repo import BaseRepo


class ManticoreRepo(BaseRepo):
    
    async def search(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[dict[str, Any]]]:
        return (0, [])

    async def aggregate(
        self, query: Query, user_shortname: str | None = None
    ) -> list[dict[str, Any]]:
        return []
    
    async def find(self, dto: EntityDTO) -> None | Meta:
        return Meta(shortname="", owner_shortname="")
    
    async def create(
        self, dto: EntityDTO, meta: Meta, payload: dict[str, Any] | None = None
    ) -> None:
        pass
    
    async def generate_payload_string(
        self,
        dto: EntityDTO,
        payload: dict[str, Any],
    ) -> str:
        return ""
    
    async def update(
        self, dto: EntityDTO, meta: Meta, payload: dict[str, Any] | None = None
    ) -> None:
        pass
    
    async def db_doc_to_record(
        self,
        space_name: str,
        db_entry: dict,
        retrieve_json_payload: bool = False,
        retrieve_attachments: bool = False,
        filter_types: list | None = None,
    ) -> Record:
        return Record()
    
    async def tags_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        return (0, [])

    async def random_query(
        self, query: Query, user_shortname: str | None = None
    ) -> tuple[int, list[Record]]:
        return (0, [])

    
