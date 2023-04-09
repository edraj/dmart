import re


SUBPATH = r"^[\w\/]{1,64}$"
SHORTNAME = r"^\w{1,32}$"
FILENAME = re.compile(r"^\w{1,32}\.(gif|png|jpeg|jpg|pdf|wsq|mp3)$")
SPACENAME = r"^\w{1,32}$"
EXT = r"^(gif|png|jpeg|jpg|json|md|pdf|wsq|mp3)$"
IMG_EXT = r"^(gif|png|jpeg|jpg|wsq)$"
USERNAME = r"^\w{3,10}$"
# PASSWORD = r"^[\w._]{4,}$"
PASSWORD = r"^(?=.*\d)(?=.*[A-Z])[a-zA-Z\d_#@%\*\-!?$^]{8,24}$"
EMAIL = r"^[\w\.-]+@([\w-]+\.)+[\w-]{2,4}$"
META_DOC_ID = r"^\w*:\w*:meta:[\w\/]+$"
MSISDN = r"^[1-9]\d{9}$"  # Exactly 10 digits, not starting with zero
EXTENDED_MSISDN = r"^[1-9]\d{9,14}$"  # Between 10 and 14 digits, not starting with zero
OTP_CODE = r"^\d{6}$"  # Exactly 6 digits
INVITATION = r"^([a-zA-Z0-9_=]+)\.([a-zA-Z0-9_=]+)\.([a-zA-Z0-9_\-\+\/=]*)$"

ATTACHMENT_FULL_PATTERN = re.compile("\.dm\/([a-zA-Z0-9_]*)\/attachments\.(\w+)\.*\w*\/meta\.(\w*)\.json$")
FILE_PATTERN = re.compile("\\.dm\\/([a-zA-Z0-9_]*)\\/meta\\.([a-zA-z]*)\\.json$")
PAYLOAD_FILE_PATTERN = re.compile("([a-zA-Z0-9_]*)\\.json$")
HISTORY_PATTERN = re.compile("([0-9]*)\\.json$")
ATTACHMENT_PATTERN = re.compile(r"attachments\.*\w*\.(\w+)\/meta\.(\w*)\.json$")
FOLDER_PATTERN = re.compile("\\/([a-zA-Z0-9_]*)\\/.dm\\/meta.folder.json$")
SPACES_PATTERN = re.compile("\\/([a-zA-Z0-9_]*)\\/.dm\\/meta.space.json$")
