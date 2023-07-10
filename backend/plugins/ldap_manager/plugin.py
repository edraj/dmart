from fastapi.logger import logger
from models.core import Event, PluginBase, User
import ldap
from models.enums import ActionType
from utils.helpers import pp
from utils.settings import settings
from utils.db import load


class Plugin(PluginBase):

    def __init__(self) -> None:
        super().__init__()
        self.con = None
        try:
            self.con = ldap.initialize(settings.ldap_url)
            self.con.simple_bind_s(settings.ldap_admin_dn, settings.ldap_pass)
        except Exception:
            logger.error(
                "Failed to connect to LDAP"
            )
            
        

    async def hook(self, data: Event):
        if not self.con:
            return
        
        # Type narrowing for PyRight
        if not isinstance(data.shortname, str):
            logger.warning(
                "data.shortname is None and str is required at ldap_manager"
            )
            return
        
        if data.action_type == ActionType.delete:
            self.con.delete_s(
                dn=f"cn={data.shortname},{settings.ldap_root_dn}"
            )
            return
        
        user_model: User = await load(
            space_name=settings.management_space,
            subpath=data.subpath,
            branch_name=settings.management_space_branch,
            shortname=data.shortname,
            class_type=User
        )
        
        if data.action_type == ActionType.create:
            self.con.add_s(
                dn=f"cn={data.shortname},{settings.ldap_root_dn}",
                modlist=[
                    ("objectClass", [b"dmartUser"]),
                    ("cn", data.shortname.encode()),
                    ("sn", data.shortname.encode()),
                    ("gn", str(getattr(user_model, "displayname", "")).encode()),
                    ("userPassword", getattr(user_model, "password", "").encode())
                ]
            )
            
        elif data.action_type in [ActionType.update, ActionType.move]:
            self.con.modify_s(
                dn=f"cn={data.shortname},{settings.ldap_root_dn}",
                modlist=[
                    # pyright doesn't identify ldap.MOD_REPLACE
                    (ldap.MOD_REPLACE, "cn", data.shortname.encode()), #type: ignore
                    (ldap.MOD_REPLACE, "sn", data.shortname.encode()), #type: ignore
                    (
                        ldap.MOD_REPLACE, #type: ignore
                        "gn", 
                        str(getattr(user_model, "displayname", "")).encode()
                    ),
                    (
                        ldap.MOD_REPLACE, #type: ignore
                        "userPassword", 
                        getattr(user_model, "password", "").encode()
                    ) 
                ]

            )