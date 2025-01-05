from data_adapters.adapter import AVAILABLE_DATA_REPOSITORIES
from data_adapters.file.file_adapter import FileAdapter
from data_adapters.sql.sql_adapter import SQLAdapter
from utils.settings import settings

def test_available_data_repositories():
    # Test if AVAILABLE_DATA_REPOSITORIES contains the correct classes
    assert 'file' in AVAILABLE_DATA_REPOSITORIES
    assert 'sql' in AVAILABLE_DATA_REPOSITORIES
    assert AVAILABLE_DATA_REPOSITORIES['file'] == FileAdapter
    assert AVAILABLE_DATA_REPOSITORIES['sql'] == SQLAdapter

def test_data_adapter_initialization():
    old_active_data_db = settings.active_data_db
    # Set the active_data_db setting directly
    settings.active_data_db = 'file'
    data_adapter_instance = AVAILABLE_DATA_REPOSITORIES[settings.active_data_db]()
    assert isinstance(data_adapter_instance, FileAdapter)

    settings.active_data_db = 'sql'
    data_adapter_instance = AVAILABLE_DATA_REPOSITORIES[settings.active_data_db]()
    assert isinstance(data_adapter_instance, SQLAdapter)

    settings.active_data_db = old_active_data_db