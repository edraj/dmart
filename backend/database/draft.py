from sqlmodel import create_engine, Session, select, func
from database.create_tables import Permissions
from utils.settings import settings

try:
    postgresql_url = f"{settings.database_driver}://{settings.database_username}:{settings.database_password}@{settings.database_host}:{settings.database_port}"
    engine = create_engine(f"{postgresql_url}/{settings.database_name}", echo=True)

    with Session(engine) as session:
        # r = session.query(Permissions).filter(Permissions.displayname['en'] == 'manage_sub_dealer').all()
        # r = select(Permissions).filter(
        #     func.to_tsvector(getattr(Permissions, 'displayname')).match('manage_sub_dealer')
        # )
        # r = select(Permissions).filter('manage_sub_dealer')
        r = select(Permissions).filter(
            func.to_tsvector(getattr(Permissions, 'displayname')).match('manage_sub_dealer')
        )
        x = session.exec(r).all()
        print(x)

except Exception as e:
    print(e)
