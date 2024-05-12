from repositories.base_repo import BaseRepo
from repositories.manticore_repo import ManticoreRepo
from repositories.redis_repo import RedisRepo
from utils.settings import settings

AVAILABLE_OPERATIONAL_REPOSITORIES: dict[str, BaseRepo] = {
    'redis': RedisRepo(),
    'manticore': ManticoreRepo()
}

class OperationalRepo:
    def __init__(self, repo: BaseRepo) -> None:
        self.repo = repo

active_repo: BaseRepo = RedisRepo()

if settings.active_operational_db != "redis" and settings.active_operational_db in AVAILABLE_OPERATIONAL_REPOSITORIES.keys():
    active_repo = AVAILABLE_OPERATIONAL_REPOSITORIES[settings.active_operational_db]

operational_repo: BaseRepo = OperationalRepo(active_repo).repo