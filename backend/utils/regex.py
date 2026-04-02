import re

SUBPATH = "^[a-zA-Z\u0621-\u064a0-9\u0660-\u0669\u064b-\u065f_/]{1,128}$"
SHORTNAME = "^[a-zA-Z\u0621-\u064a0-9\u0660-\u0669\u064b-\u065f_]{1,64}$"
SLUG = "^[a-zA-Z0-9_-]{1,64}$"
FILENAME = "^[a-zA-Z\u0621-\u064a0-9\u0660-\u0669\u064b-\u065f_]{1,32}\\.(gif|png|jpeg|jpg|pdf|wsq|mp3|mp4|csv|jsonl|parquet|sqlite|sqlite3|sqlite|db|duckdb|svg|apk)$"
SPACENAME = "^[a-zA-Z\u0621-\u064a0-9\u0660-\u0669\u064b-\u065f_]{1,32}$"
EXT = "^(gif|png|jpeg|jpg|webp|json|md|pdf|wsq|mp3|mp4|csv|jsonl|parquet|sqlite|sqlite3|db|db3|s3db|sl3|duckdb|svg|xlsx|docx|apk)$"
IMG_EXT = "^(gif|png|jpeg|jpg|wsq|svg|webp)$"
USERNAME = "^[a-zA-Z\u0621-\u064a0-9\u0660-\u0669\u064b-\u065f_]{3,10}$"
PASSWORD = "^(?=.*[0-9\u0660-\u0669])(?=.*[A-Z\u0621-\u064a])[a-zA-Z\u0621-\u064a0-9\u0660-\u0669 _#@%*!?$^&()+={}\\[\\]~|;:,.<>/-]{8,64}$"
EMAIL = (
    "^[a-z0-9_\\.-]+@([a-z0-9_-]+\\.)+"
    "[a-z0-9]{2,4}$"
)
META_DOC_ID = (
    "^[a-zA-Z\u0621-\u064a0-9\u0660-\u0669_]*:[a-zA-Z\u0621-\u064a0-9\u0660-\u0669_]"
    "[a-zA-Z\u0621-\u064a0-9\u0660-\u0669_]*:meta:[a-zA-Z\u0621-\u064a0-9\u0660-\u0669_/]+$"
)
MSISDN = "^[1-9][0-9]{9,14}$"  # Between 10 and 14 digits, not starting with zero
EXTENDED_MSISDN = "^[1-9][0-9]{9,14}$"  # Between 10 and 14 digits, not starting with zero
OTP_CODE = "^[0-9\u0660-\u0669]{6}$"  # Exactly 6 digits
INVITATION = (
    "^([a-zA-Z\u0621-\u064a0-9\u0660-\u0669_=]+)\\.([a-zA-Z\u0621-\u064a0-9\u0660-\u0669_=]+)"
    "\\.([a-zA-Z\u0621-\u064a0-9\u0660-\u0669_+/=-]*)$"
)

FILE_PATTERN = re.compile("\\.dm/([a-zA-Z\u0621-\u064a0-9\u0660-\u0669_]*)/meta\\.([a-zA-Z\u0621-\u064a]*)\\.json$")
PAYLOAD_FILE_PATTERN = re.compile("([a-zA-Z\u0621-\u064a0-9\u0660-\u0669_]*)\\.json$")
# HISTORY_PATTERN = re.compile("([0-9\u0660-\u0669]*)\\.json$")
ATTACHMENT_PATTERN = re.compile(
    "attachments\\.*[a-zA-Z\u0621-\u064a0-9\u0660-\u0669_]*\\.([a-zA-Z\u0621-\u064a0-9\u0660-\u0669_]+)"
    "/meta\\.([a-zA-Z\u0621-\u064a0-9\u0660-\u0669_]*)\\.json$"
)
FOLDER_PATTERN = re.compile("/([a-zA-Z\u0621-\u064a0-9\u0660-\u0669\u064b-\u065f_]*)/\\.dm/meta\\.folder\\.json$")
SPACES_PATTERN = re.compile("/([a-zA-Z\u0621-\u064a0-9\u0660-\u0669\u064b-\u065f_]*)/\\.dm/meta\\.space\\.json$")
