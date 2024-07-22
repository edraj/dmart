import pytest
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock
import aiofiles
import pytest
from models.core import User, Payload
from httpx import AsyncClient


@pytest.fixture
async def unique_user_data():
    unique_user_shortname = "unique_testuser"
    existing_user_data = {
        'shortname': unique_user_shortname,
        'password': 'oldhashedpassword',
        'owner_shortname': 'owner'
    }
    return unique_user_shortname, existing_user_data

