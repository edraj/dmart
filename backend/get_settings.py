#!/usr/bin/env -S BACKEND_ENV=config.env python3.11

import json
from utils.settings import settings


if __name__ == "__main__":
    print(settings.json())
