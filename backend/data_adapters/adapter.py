from typing import Type

from .base_data_adapter import BaseDataAdapter  # type: ignore
from .file_adapter import FileAdapter  # type: ignore
from .sql_adapter import SQLAdapter  # type: ignore
from utils.settings import settings


AVAILABLE_DATA_REPOSITORIES: dict[str, Type[SQLAdapter | FileAdapter]] = {
    'file': FileAdapter,
    'sql': SQLAdapter
}

data_adapter: BaseDataAdapter = AVAILABLE_DATA_REPOSITORIES[settings.active_data_db]()
