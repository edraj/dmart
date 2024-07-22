import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
from health_check import main, print_health_check, cleanup_spaces, \
    save_health_check_entry, print_header, load_spaces_schemas

# @pytest.mark.asyncio
# @patch("health_check.os")
# @patch("health_check.Path")
# async def test_cleanup_spaces(mock_path, mock_os):
#     mock_os.path.isdir.return_value = True
#     mock_path.return_value.is_file.return_value = True
#
#     await cleanup_spaces()
#
#     mock_os.remove.assert_called()


@pytest.mark.asyncio
@patch("health_check.serve_request", new_callable=AsyncMock)
async def test_save_health_check_entry(mock_serve_request):
    health_check = {
        "folders_report": {"test_schema": {"valid_entries": 1, "invalid_entries": []}}
    }

    await save_health_check_entry(health_check, "test_space")

    mock_serve_request.assert_called()

def test_print_header(capfd):
    print_header()
    captured = capfd.readouterr()
    assert "subpath" in captured.out
    assert "valid" in captured.out
    assert "invalid" in captured.out

def test_print_health_check(capfd):
    health_check = {
        "folders_report": {
            "test_schema": {
                "valid_entries": 1,
                "invalid_entries": [
                    {
                        "shortname": "invalid1",
                        "issues": ["issue1"],
                        "exception": "exception1"
                    }
                ]
            }
        },
        "invalid_folders": ["invalid_folder1"]
    }

    print_health_check(health_check)
    captured = capfd.readouterr()
    assert "test_schema" in captured.out
    assert "invalid1" in captured.out
    assert "issue1" in captured.out
    assert "exception1" in captured.out
    assert "invalid_folder1" in captured.out

@pytest.mark.asyncio
@patch("health_check.get_spaces", new_callable=AsyncMock)
async def test_load_spaces_schemas(mock_get_spaces):
    mock_get_spaces.return_value = {
        "test_space": json.dumps({
            "shortname": "test_space",
            "owner_shortname": "owner",
            "check_health": True
        })
    }

    schemas = await load_spaces_schemas("test_space")
    assert "test_space" in schemas

