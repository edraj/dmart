#!/usr/bin/env -S BACKEND_ENV=config.env python3
import asyncio
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: migrate.py <json_to_db|db_to_json>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "json_to_db":
        import data_adapters.sql.json_to_db_migration as json_to_db_migration
        asyncio.run(json_to_db_migration.main())
    elif command == "db_to_json":
        import data_adapters.sql.db_to_json_migration as db_to_json_migration
        db_to_json_migration.main()
    else:
        print("Invalid command. Use 'json_to_db' or 'db_to_json'.")
        sys.exit(1)

if __name__ == "__main__":
    main()