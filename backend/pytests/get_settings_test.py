# test_script.py
import subprocess
import pytest


@pytest.mark.run(order=4)
def test_script_execution():
    result = subprocess.run(
        ['python3', 'get_settings.py'],
        capture_output=True,
        text=True,
        check=True
    )
    assert result.returncode == 0