
from utils.settings import settings

from .base_data_adapter import BaseDataAdapter
from .file.adapter import FileAdapter
from .sql.adapter import SQLAdapter

AVAILABLE_DATA_REPOSITORIES: dict[str, type[SQLAdapter | FileAdapter]] = {"file": FileAdapter, "sql": SQLAdapter}

data_adapter: BaseDataAdapter = AVAILABLE_DATA_REPOSITORIES[settings.active_data_db]()

# asyncio.run(data_adapter.test_connection())
