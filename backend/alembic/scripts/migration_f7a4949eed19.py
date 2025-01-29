#!/usr/bin/env -S BACKEND_ENV=config.env python3
from sqlmodel import select

from data_adapters.sql.adapter import SQLAdapter
from data_adapters.sql.create_tables import Entries, Permissions, Roles, Spaces, Users
from utils.query_policies_helper import generate_query_policies


print("[INFO]  [dmart.script] Performing post-upgrade data migration (calc-query-policies)")
with SQLAdapter().get_session() as session:
    for table in [Entries, Permissions, Roles, Spaces, Users]:
        print(f"[INFO]  [dmart.script] Processing table: {table}")
        records = session.exec(select(table)).all()
        print(f"[INFO]  [dmart.script] Processing {len(records)} records")
        for record in records:
            if not record.query_policies:
                record.query_policies = generate_query_policies(
                    space_name=record.space_name,
                    subpath=f"{record.subpath}/{record.shortname}" if record.resource_type == 'folder' else record.subpath,
                    resource_type=record.resource_type,
                    is_active=record.is_active,
                    owner_shortname=record.owner_shortname,
                    owner_group_shortname= record.owner_group_shortname if  hasattr(record, 'owner_group_shortname') else "",
                )
                session.add(record)
                print(".", end="\r")
        session.commit()
print("[INFO]  [dmart.script] Post-upgrade data migration completed")
