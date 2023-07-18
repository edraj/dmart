""" Application Settings """

import os
import string
import random
from pydantic import BaseSettings  # BaseModel,
from pathlib import Path


class Settings(BaseSettings):
    """Main settings class"""

    app_url: str = ""
    public_app_url: str = ""
    websocket_url: str = "http://127.0.0.1:8484"
    websocket_port: int = 8484
    base_path: str = ""
    debug_enabled: bool = True
    log_handlers: list[str] = ["console", "file"]
    log_file: str = "../logs/dmart.ljson.log"
    ws_log_file: str = "../logs/websocket.ljson.log"
    jwt_secret: str = "".join(random.sample(string.ascii_letters + string.digits, 12))
    jwt_algorithm: str = "HS256"
    jwt_access_expires: int = 30 * 86400  # 30 days
    listening_host: str = "0.0.0.0"
    listening_port: int = 8282
    redis_host: str = "127.0.0.1"
    redis_password: str = ""
    redis_port: int = 6379
    management_space: str = "management"
    users_subpath: str = "users"
    spaces_folder: Path = Path("../sample/spaces/")
    lock_period: int = 300
    servername: str = ""  # This is for print purposes only.
    auto_uuid_rule = "auto"  # Used to generate a shortname from UUID
    google_application_credentials = ""
    default_branch = "master"
    management_space_branch = "master"
    all_spaces_mw = (
        "__all_spaces__"  # magic word used in access control refers to any space
    )
    all_subpaths_mw = (
        "__all_subpaths__"  # used in access control refers to all subpaths
    )
    current_user_mw = (
        "__current_user__"  # used in access control refers to current logged-in user
    )
    root_subpath_mw = "__root__"
    email_sender = "dmart@dmart.com"

    otp_token_ttl: int = 60 * 2
    comms_api: str = ""
    mock_smtp_api: bool = True
    mock_smpp_api: bool = False
    invitation_link: str = ""
    ldap_url: str = "ldap://"
    ldap_admin_dn: str = ""
    ldap_root_dn: str = ""
    ldap_pass: str = ""

    class Config:
        """Load config"""

        env_file = os.getenv("BACKEND_ENV", "config.env")
        env_file_encoding = "utf-8"


settings = Settings()
