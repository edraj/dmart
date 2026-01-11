#!/usr/bin/env -S BACKEND_ENV=config.env python3
import asyncio
import hashlib
import json
from datetime import datetime
from sqlalchemy import select, update, func
from data_adapters.sql.adapter import SQLAdapter
from data_adapters.sql.create_tables import Histories, Users, Entries, Spaces, Roles, Permissions

def flatten_dict(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

async def migrate_checksums():
    db = SQLAdapter()
    
    async with db.get_session() as session:
        resource_tables = [Users, Permissions, Roles, Entries, Spaces]
        
        for resource_table in resource_tables:
            print(f"Processing table: {resource_table.__tablename__}")
            
            # Fetch all records from the current table
            stmt = select(resource_table)
            result = await session.execute(stmt)
            records = result.scalars().all()
            
            print(f"Found {len(records)} records in {resource_table.__tablename__}")

            batch_size = 1000
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                print(f"Processing batch {i // batch_size + 1} ({len(batch)} records) for {resource_table.__tablename__}...")
                
                for record in batch:
                    try:
                        async with session.begin_nested():
                            record_dict = record.model_dump()
                            flat_record = flatten_dict(record_dict)

                            new_version_json = json.dumps(flat_record, sort_keys=True, default=str)
                            new_checksum = hashlib.sha1(new_version_json.encode()).hexdigest()

                            record.last_checksum_history = new_checksum
                            session.add(record)

                            history_stmt = select(Histories).where(
                                Histories.space_name == record.space_name,
                                Histories.subpath == record.subpath,
                                Histories.shortname == record.shortname
                            ).order_by(Histories.timestamp.desc()).limit(1)
                            
                            history_result = await session.execute(history_stmt)
                            latest_history = history_result.scalars().first()

                            if latest_history:
                                latest_history.last_checksum_history = new_checksum
                                session.add(latest_history)
                            else:
                                print(f"No history found for {record.space_name}/{record.subpath}/{record.shortname}")
                    
                    except Exception as e:
                        print(f"Error processing {record.space_name}/{record.shortname} in {resource_table.__tablename__}: {e}")
                
                await session.commit()
                print(f"Batch {i // batch_size + 1} committed for {resource_table.__tablename__}.")
        
        print("Migration completed.")

if __name__ == "__main__":
    asyncio.run(migrate_checksums())
