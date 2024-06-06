from sqlalchemy import text
from sqlmodel import SQLModel, create_engine, Field, Session

from database.create_tables import Entries

postgresql_url = "postgresql://postgres:tenno1515@localhost:5432/management"
engine = create_engine(postgresql_url, echo=True)
s = Session(engine)
r = s.exec(
    text(
        f"select * from entries where subpath='schema' and shortname='view';"
    )
).all()
print(
    Entries.model_validate(r[0]).model_dump()
)
print(Entries.model_validate(r[0]).model_dump().get('payload', {}))
