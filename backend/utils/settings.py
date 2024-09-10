""" Application Settings """

import json
import os
import re
import string
import random
from venv import logger
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
    redis_pool_max_connections: int = 20
    one_session_per_user: bool = False
    management_space: str = "management"
    users_subpath: str = "users"
    spaces_folder: Path = Path("../sample/spaces/")
    lock_period: int = 300
    servername: str = ""  # This is for print purposes only.
    auto_uuid_rule: str = "auto"  # Used to generate a shortname from UUID
    google_application_credentials: str = ""
    is_registrable: bool = True
    social_login_allowed: bool = True
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
    send_sms_otp_api: str = ""
    send_email_otp_api: str = ""
    send_sms_api: str = ""
    send_email_api: str = ""
    mock_smtp_api: bool = True
    files_query: str = "scandir"
    mock_smpp_api: bool = True
    invitation_link: str = ""
    ldap_url: str = "ldap://"
    ldap_admin_dn: str = ""
    ldap_root_dn: str = ""
    ldap_pass: str = ""
    max_query_limit: int = 10000
    session_inactivity_ttl: int = 60 * 60 * 24 * 7  # 7 days

    url_shorter_expires: int = 60 * 60 * 48  # 48 hours

    google_client_id: str = ""
    google_client_secret: str = ""

    facebook_client_id: str = ""
    facebook_client_secret: str = ""
    
    enable_channel_auth: bool = False
    channels: list = []
    store_payload_string: bool = True

    active_operational_db: str = "redis"  # allowed values: redis, manticore
    active_data_db: str = "file"  # allowed values: file, sql

    database_driver: str = 'postgresql'
    database_username: str = 'postgres'
    database_password: str = ''
    database_host: str = 'localhost'
    database_port: int = 5432
    database_name: str = 'dmart'

    max_failed_login_attempts: int = 5

    model_config = SettingsConfigDict(
        env_file=os.getenv(
            "BACKEND_ENV",
            str(Path(__file__).resolve().parent.parent.parent / "config.env") if __file__.endswith(".pyc") else "config.env"
        ), env_file_encoding="utf-8"
    )
    
    def load_config_files(self) -> None:
        channels_config_file = os.path.join(os.path.dirname(__file__), '../config/channels.json')
        if os.path.exists(channels_config_file):
            try:
                with open(channels_config_file, 'r') as file:
                    self.channels = json.load(file)
                
                # Compile the patterns for better performance
                for idx, channel in enumerate(self.channels):
                    compiled_patterns: list[re.Pattern] = []
                    for pattern in channel.get("allowed_api_patterns", []):
                        compiled_patterns.append(re.compile(pattern))
                    self.channels[idx]["allowed_api_patterns"] = compiled_patterns
                    
            except Exception as e:
                logger.error(f"Failed to open the channel config file at {channels_config_file}. Error: {e}")    
        
        


settings = Settings()
settings.load_config_files()
