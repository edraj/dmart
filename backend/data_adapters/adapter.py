from base_data_adapter import BaseDataAdapter
from file_adapter import FileAdapter
from sql_adapter import SQLAdapter
from utils.settings import settings


AVAILABLE_DATA_REPOSITORIES: dict[str, BaseDataAdapter] = {
    'file': FileAdapter(),
    'postgres': SQLAdapter()
}


class DataAdapter:
    def __init__(self, adapter: BaseDataAdapter) -> None:
        self.adapter = adapter


active_data_adapter = AVAILABLE_DATA_REPOSITORIES[settings.active_data_db]
data_adapter: BaseDataAdapter = DataAdapter(active_data_adapter).adapter
