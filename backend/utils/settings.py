""" Application Settings """

import json
import os
import re
import string
import random
from venv import logger

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Main settings class"""

    app_url: str = ""
    public_app_url: str = ""
    app_name: str = "dmart"
    websocket_url: str = "" #"http://127.0.0.1:8484"
    websocket_port: int = 8484
    base_path: str = ""
    debug_enabled: bool = True
    log_handlers: list[str] = ['file']
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
    max_sessions_per_user: int = 5
    management_space: str = "management"
    users_subpath: str = "users"
    spaces_folder: Path = Path("../sample/spaces/")
    lock_period: int = 300
    auto_uuid_rule: str = "auto"  # Used to generate a shortname from UUID
    google_application_credentials: str = ""
    is_registrable: bool = True
    is_otp_for_create_required: bool = True
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
    allow_otp_resend_after: int = 60
    comms_api: str = ""
    send_sms_otp_api: str = ""
    smpp_auth_key: str = ""
    send_email_otp_api: str = ""
    send_sms_api: str = ""
    send_email_api: str = ""
    mock_smtp_api: bool = True
    files_query: str = "scandir"
    mock_smpp_api: bool = True
    mock_otp_code: str = "123456"
    invitation_link: str = ""
    ldap_url: str = "ldap://"
    ldap_admin_dn: str = ""
    ldap_root_dn: str = ""
    ldap_pass: str = ""
    max_query_limit: int = 10000
    session_inactivity_ttl: int = 0 # Set initially to 0 to disable session timeout. Possible value : 60 * 60 * 24 * 7  # 7 days
    request_timeout: int = 35 # In seconds the time of dmart requests.
    jq_timeout: int = 2 # secs
    is_sha_required: bool = False

    url_shorter_expires: int = 60 * 60 * 48  # 48 hours

    google_client_id: str = ""
    google_client_secret: str = ""
    apple_client_id: str = ""
    apple_client_secret: str = ""

    facebook_client_id: str = ""
    facebook_client_secret: str = ""
    
    enable_channel_auth: bool = False
    channels: list = []
    store_payload_string: bool = True

    active_operational_db: str = "redis"  # allowed values: redis, manticore
    active_data_db: str = "file"  # allowed values: file, sql

    database_driver: str = 'postgresql+psycopg'
    database_username: str = 'postgres'
    database_password: str = ''
    database_host: str = 'localhost'
    database_port: int = 5432
    database_name: str = 'dmart'
    database_pool_size: int = 2
    database_max_overflow: int = 2
    database_pool_timeout: int = 30
    database_pool_recycle: int = 30

    hide_stack_trace: bool = False
    max_failed_login_attempts: int = 5


    model_config = SettingsConfigDict(
        env_file=os.getenv(
            "BACKEND_ENV",
            str(Path(__file__).resolve().parent.parent.parent / "config.env") if __file__.endswith(".pyc") else "config.env"
        ), env_file_encoding="utf-8"
    )
    
    def load_config_files(self) -> None:
        channels_config_file = Path(__file__).resolve().parent.parent / 'config/channels.json'
        if channels_config_file.exists():
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

    raw_allowed_submit_models: str = Field(default="",alias="allowed_submit_models")

    @property
    def allowed_submit_models(self) -> dict[str, list[str]]:
        allowed_models_str = self.raw_allowed_submit_models
        result: dict = {}
        if allowed_models_str:
            entries = allowed_models_str.split(",")
            for entry in entries:
                entry = entry.strip()
                if "." in entry:
                    space, schema = entry.split(".", 1)
                    if space not in result:
                        result[space] = []
                    result[space].append(schema)
        return result

try:
    Settings.model_validate(
        Settings()
    )
except Exception as e:
    logger.error(f"Failed to load settings.\nError: {e}")
    # sys.exit(1)
    pass

settings = Settings()
settings.load_config_files()
