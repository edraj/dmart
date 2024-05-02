
from typing import Any
from db.base_db import BaseDB
import manticoresearch
from fastapi.logger import logger
from utils.settings import settings


class ManticoreDB(BaseDB):
    config = manticoresearch.Configuration(
        host = "{settings.operational_db_host}:{settings.operational_db_port}",
        username=settings.operational_db_user,
        password=settings.operational_db_password
    )
    client = manticoresearch.ApiClient(config)
    indexApi = manticoresearch.IndexApi(client)
    searchApi = manticoresearch.SearchApi(client)
    utilsApi = manticoresearch.UtilsApi(client)
    
    async def flush_all(self) -> None:
        try:
            tables = self.utilsApi.sql('SHOW TABLES') 
            if(
                not isinstance(tables, list) or 
                len(tables) == 0 or 
                not isinstance(tables[0], dict)
            ):
                return
            
            for table in tables[0].get('data', []):
                self.utilsApi.sql(f'DROP TABLE {table['Index']}')
                
        except Exception as e:
            logger.error(f"Error at ManticoreDB.flush_all: {e.args}")
            
        
    