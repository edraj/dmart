from typing import Type

from .base_data_adapter import BaseDataAdapter  # type: ignore
from .file_adapter import FileAdapter  # type: ignore
from .sql_adapter import SQLAdapter  # type: ignore
from utils.settings import settings


AVAILABLE_DATA_REPOSITORIES: dict[str, Type[SQLAdapter | FileAdapter]] = {
    'file': FileAdapter,
    'sql': SQLAdapter
}


class DataAdapter:
    def __init__(self, adapter: BaseDataAdapter) -> None:
        self.adapter = adapter


active_data_adapter = AVAILABLE_DATA_REPOSITORIES[settings.active_data_db]
data_adapter: BaseDataAdapter = DataAdapter(active_data_adapter()).adapter
