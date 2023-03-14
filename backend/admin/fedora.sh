#!bin/bash

# Useful tools
sudo dnf install jq

# Python dependencies available in fedora
sudo dnf install python3-multipart python3-aiohttp python3-pydantic python3-json-logger python3-redis python3-jwt python3-fastapi python3-aiofiles

# Python dependencies not availble in fedora
pip install --user hypercorn concurrent_log_handler jq pydantic[dotenv]


# Pytest packages
sudo dnf install python3-pytest-mock python3-pytest python3-pytest-httpx python3-pytest-asyncio

# ?? python3-jsonschema

# For cli
sudo dnf install python3-rich python3-prompt-toolkit python3-typer

