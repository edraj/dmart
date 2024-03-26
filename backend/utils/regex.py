import re

SUBPATH = "^[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_/]{1,128}$"
SHORTNAME = "^[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]{1,64}$"
FILENAME = "^[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]{1,32}\\.(gif|png|jpeg|jpg|pdf|wsq|mp3|mp4|csv|jsonl|parquet|sqlite|sqlite3|sqlite|db|duckdb|svg)$"
SPACENAME = "^[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]{1,32}$"
EXT = "^(gif|png|jpeg|jpg|json|md|pdf|wsq|mp3|mp4|csv|jsonl|parquet|sqlite|sqlite3|db|db3|s3db|sl3|duckdb|svg)$"
IMG_EXT = "^(gif|png|jpeg|jpg|wsq|svg)$"
USERNAME = "^[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]{3,10}$"
PASSWORD = "^(?=.*[0-9\u0660-\u0669])(?=.*[A-Z\u0621-\u064A])[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_#@%*!?$^-]{8,24}$"
EMAIL = (
    "^[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_\\.-]+@([a-zA-Z\u0621-\u064A0-9\u0660-\u0669_-]+\\.)+"
    "[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_-]{2,4}$"
)
META_DOC_ID = (
    "^[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]*:[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]"
    "[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]*:meta:[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_/]+$"
)
MSISDN = "^[1-9][0-9]{9}$"  # Exactly 10 digits, not starting with zero
EXTENDED_MSISDN = (
    "^[1-9][0-9]{9,14}$"  # Between 10 and 14 digits, not starting with zero
)
OTP_CODE = "^[0-9\u0660-\u0669]{6}$"  # Exactly 6 digits
INVITATION = (
    "^([a-zA-Z\u0621-\u064A0-9\u0660-\u0669_=]+)\\.([a-zA-Z\u0621-\u064A0-9\u0660-\u0669_=]+)"
    "\\.([a-zA-Z\u0621-\u064A0-9\u0660-\u0669_+/=-]*)$"
)

FILE_PATTERN = re.compile(
    "\\.dm/([a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]*)/meta\\.([a-zA-Z\u0621-\u064A]*)\\.json$"
)
PAYLOAD_FILE_PATTERN = re.compile("([a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]*)\\.json$")
# HISTORY_PATTERN = re.compile("([0-9\u0660-\u0669]*)\\.json$")
ATTACHMENT_PATTERN = re.compile(
    "attachments\\.*[a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]*\\.([a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]+)"
    "/meta\\.([a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]*)\\.json$"
)
FOLDER_PATTERN = re.compile(
    "/([a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]*)/\\.dm/meta\\.folder\\.json$"
)
SPACES_PATTERN = re.compile(
    "/([a-zA-Z\u0621-\u064A0-9\u0660-\u0669_]*)/\\.dm/meta\\.space\\.json$"
)
