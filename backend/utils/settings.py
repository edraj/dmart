""" Application Settings """

import os
import string
import random
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Main settings class"""

    app_url: str = ""
    public_app_url: str = ""
    app_name: str = "dmart"
    websocket_url: str = "" # http://127.0.0.1:8484"
    websocket_port: int = 8484
    base_path: str = ""
    debug_enabled: bool = True
    log_handlers: list[str] = ['console', 'file']
    log_file: str = "../logs/dmart.ljson.log"
    ws_log_file: str = "../logs/websocket.ljson.log"
    jwt_secret: str = "".join(random.sample(string.ascii_letters + string.digits,12))
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
    auto_uuid_rule: str = "auto"  # Used to generate a shortname from UUID
    google_application_credentials: str = ""
    default_branch: str = "master"
    management_space_branch: str = "master"
    all_spaces_mw: str = (
        "__all_spaces__"  # magic word used in access control refers to any space
    )
    all_subpaths_mw: str = (
        "__all_subpaths__"  # used in access control refers to all subpaths
    )
    current_user_mw: str = (
        "__current_user__"  # used in access control refers to current logged-in user
    )
    root_subpath_mw : str = "__root__"
    email_sender: str = "dmart@dmart.com"

    otp_token_ttl: int = 60 * 5
    comms_api: str = ""
    mock_smtp_api: bool = True
    files_query: str = "scandir"
    mock_smpp_api: bool = False
    invitation_link: str = ""
    ldap_url: str = "ldap://"
    ldap_admin_dn: str = ""
    ldap_root_dn: str = ""
    ldap_pass: str = ""
    max_query_limit: int = 10000
    session_inactivity_ttl: int = 60 * 10

    model_config = SettingsConfigDict(env_file = os.getenv("BACKEND_ENV", "config.env"), env_file_encoding = "utf-8")

settings = Settings()
