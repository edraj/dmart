from typing import Type

from .base_data_adapter import BaseDataAdapter
from .file.adapter import FileAdapter
from .sql.adapter import SQLAdapter
from utils.settings import settings


AVAILABLE_DATA_REPOSITORIES: dict[str, Type[SQLAdapter | FileAdapter]] = {
    'file': FileAdapter,
    'sql': SQLAdapter
}

data_adapter: BaseDataAdapter = AVAILABLE_DATA_REPOSITORIES[settings.active_data_db]()

# asyncio.run(data_adapter.test_connection())
