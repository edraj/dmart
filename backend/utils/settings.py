""" Application Settings """

import json
import os
import random
import re
import string
from venv import logger

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

def get_env_file():
    env_file = os.getenv("BACKEND_ENV")

    if env_file and os.path.exists(env_file):
        return env_file
    
    if not env_file or env_file == "config.env":
        if os.path.exists("config.env"):
            return "config.env"

        dmart_home = Path.home() / ".dmart"
        home_config = dmart_home / "config.env"
        
        if home_config.exists():
            return str(home_config)

    return env_file or "config.env"

class Settings(BaseSettings):
    """Main settings class"""

    app_url: str = ""
    cxb_url: str = "/cxb"
    cxb_config_path: str = ""
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

    otp_token_ttl: int = 60 * 5
    allow_otp_resend_after: int = 60
    comms_api: str = ""
    send_sms_otp_api: str = ""
    smpp_auth_key: str = ""
    sms_sender: str = ""
    send_sms_api: str = ""
    mock_smtp_api: bool = True

    mail_driver: str = "smtp"
    mail_host: str = ""
    mail_port: int = 587
    mail_username: str = ""
    mail_password: str = ""
    mail_encryption: str = "tls"
    mail_from_address: str = "noreply@admin.com"
    mail_from_name: str = ""

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
    logout_on_pwd_change: bool = True
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

    database_driver: str = 'sqlite+pysqlite'
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
        env_file=get_env_file(),
        env_file_encoding="utf-8"
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
        
        self.load_cxb_config()

    def load_cxb_config(self) -> None:
        backend_dir = Path(__file__).resolve().parent.parent
        cxb_path = backend_dir / "cxb"
        if (cxb_path / "client").is_dir():
            cxb_path = cxb_path / "client"
        
        if not (cxb_path / "index.html").exists():
            project_root = backend_dir.parent
            cxb_dist_path = project_root / "cxb" / "dist" / "client"
            if cxb_dist_path.is_dir():
                cxb_path = cxb_dist_path

        config_path = None
        cxb_config_env = os.getenv("DMART_CXB_CONFIG")
        if cxb_config_env and os.path.exists(cxb_config_env):
            config_path = cxb_config_env
        elif os.path.exists("config.json"):
            config_path = "config.json"
        elif (self.spaces_folder / "config.json").exists():
            config_path = str(self.spaces_folder / "config.json")
        elif (Path.home() / ".dmart" / "config.json").exists():
            config_path = str(Path.home() / ".dmart" / "config.json")
        elif (cxb_path / "config.json").exists():
            config_path = str(cxb_path / "config.json")
            
        if config_path:
            self.cxb_config_path = config_path
            try:
                with open(config_path, "r") as f:
                    config_data = json.load(f)
                    if "cxb_url" in config_data:
                        url = config_data["cxb_url"]
                        if not url.startswith("/"):
                            url = "/" + url
                        self.cxb_url = url
            except Exception as e:
                logger.error(f"Failed to read CXB config at {config_path}. Error: {e}")

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
