from operational_adapters.base_repo import BaseRepo
from operational_adapters.manticore_repo import ManticoreRepo
from operational_adapters.redis_repo import RedisRepo
from utils.settings import settings

AVAILABLE_OPERATIONAL_REPOSITORIES: dict[str, BaseRepo] = {
    'redis': RedisRepo(),
    'manticore': ManticoreRepo()
}


class OperationalRepo:
    def __init__(self, repo: BaseRepo) -> None:
        self.repo = repo


active_operational_repo = AVAILABLE_OPERATIONAL_REPOSITORIES[settings.active_operational_db]
operational_repo: BaseRepo = OperationalRepo(active_operational_repo).repo
