
from .base_data_adapter import BaseDataAdapter
from .sql.adapter import SQLAdapter

AVAILABLE_DATA_REPOSITORIES: dict[str, type[SQLAdapter ]] = {"sql": SQLAdapter}

data_adapter: BaseDataAdapter = AVAILABLE_DATA_REPOSITORIES["sql"]()

# asyncio.run(data_adapter.test_connection())
