from fastapi.logger import logger
from models.core import Event, PluginBase, User
from models.enums import ActionType
from utils.settings import settings
from data_adapters.adapter import data_adapter as db

from ldap3 import AUTO_BIND_NO_TLS, MODIFY_REPLACE, Server, Connection, ALL


class Plugin(PluginBase):

    def __init__(self) -> None:
        super().__init__()
        try:
            server = Server(settings.ldap_url, get_info=ALL)
            self.conn = Connection(
                server, 
                user=settings.ldap_admin_dn, 
                password=settings.ldap_pass, 
                auto_bind=AUTO_BIND_NO_TLS
            )
        except Exception:
            logger.error(
                "Failed to connect to LDAP"
            )
            
        

    async def hook(self, data: Event):
        if not hasattr(self, "conn"):
            return
        
        # Type narrowing for PyRight
        if not isinstance(data.shortname, str):
            logger.warning(
                "data.shortname is None and str is required at ldap_manager"
            )
            return
        
        if data.action_type == ActionType.delete:
            self.delete(data.shortname)
            return
        
        user_model: User = await db.load(
            space_name=settings.management_space,
            subpath=data.subpath,
            shortname=data.shortname,
            class_type=User
        )
        
        if data.action_type == ActionType.create:
            self.add(data.shortname, user_model)
            
        elif data.action_type == ActionType.update:
            self.modify(data.shortname, user_model)
            

        elif data.action_type == ActionType.move and "src_shortname" in data.attributes:
            self.delete(data.attributes['src_shortname'])
            self.add(data.shortname, user_model)
            
            
            
    def delete(self, shortname: str):
        self.conn.delete(f"cn={shortname},{settings.ldap_root_dn}")
        
    def add(
        self, 
        shortname: str, 
        user_model: User
    ):
        self.conn.add(
            f"cn={shortname},{settings.ldap_root_dn}", 
            'dmartUser',
            {
                "cn": shortname.encode(),
                "sn": shortname.encode(),
                "gn": str(getattr(user_model, "displayname", "")).encode(),
                "userPassword": getattr(user_model, "password", "").encode()
            }
        )
        
    def modify(
        self, 
        shortname: str, 
        user_model: User
    ):
        self.conn.modify(
            f"cn={shortname},{settings.ldap_root_dn}", 
            {
                "gn": [(
                    MODIFY_REPLACE, 
                    [str(getattr(user_model, "displayname", "")).encode()]
                )],
                "userPassword": [(
                    MODIFY_REPLACE,
                    [getattr(user_model, "password", "").encode()]
                )],
            }
        )