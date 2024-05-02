from db.base_db import BaseDB
from db.redis_db import RedisDB
from utils.settings import settings

AVAILABLE_OPERATIONAL_DATABASES: dict[str, BaseDB] = {
    'redis': RedisDB()
}

class OperationalDatabase:
    def __init__(self, database: BaseDB) -> None:
        self.db = database
        
active_db: BaseDB = RedisDB()

if settings.active_operational_db != "redis" and settings.active_operational_db in AVAILABLE_OPERATIONAL_DATABASES.keys():
    active_db = AVAILABLE_OPERATIONAL_DATABASES[settings.active_operational_db]

operational_db: BaseDB = OperationalDatabase(active_db).db