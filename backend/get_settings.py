#!/usr/bin/env -S BACKEND_ENV=config.env python3

from utils.settings import settings


if __name__ == "__main__":
    print(settings.model_dump_json())
