from enum import Enum


class StrEnum(str, Enum):
    def __str__(self):
        return self.value


class RequestType(StrEnum):
    create = "create"
    update = "update"
    r_replace = "replace"
    delete = "delete"
    move = "move"


class Language(StrEnum):
    ar = "arabic"
    en = "english"
    kd = "kurdish"
    fr = "french"
    tr = "trukish"


class ResourceType(StrEnum):
    user = "user"
    group = "group"
    folder = "folder"
    schema = "schema"
    content = "content"
    acl = "acl"
    comment = "comment"
    media = "media"
    locator = "locator"
    relationship = "relationship"
    alteration = "alteration"
    history = "history"
    space = "space"
    branch = "branch"
    permission = "permission"
    role = "role"
    ticket = "ticket"
    json = "json"
    lock = "lock"
    plugin_wrapper = "plugin_wrapper"
    notification = "notification"


class ContentType(StrEnum):
    text = "text"
    markdown = "markdown"
    html = "html"
    json = "json"
    image = "image"
    python = "python"
    pdf = "pdf"
    audio = "audio"
    video = "video"

    @staticmethod
    def inline_types() -> list:
        return [
            ContentType.text,
            ContentType.markdown,
            ContentType.html
        ]


class TaskType(StrEnum):
    query = "query"


class UserType(StrEnum):
    web = "web"
    mobile = "mobile"
    bot = "bot"


class ValidationEnum(StrEnum):
    valid = "valid"
    invalid = "invalid"


class LockAction(StrEnum):
    lock = "lock"
    extend = "extend"
    unlock = "unlock"
    cancel = "cancel"


class NotificationType(StrEnum):
    admin = "admin"
    system = "system"


class NotificationPriority(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class StrBoolEnum(StrEnum):
    true = "yes"
    false = "no"


class ActionType(StrEnum):
    query = "query"
    view = "view"
    update = "update"
    create = "create"
    delete = "delete"
    attach = "attach"
    move = "move"
    progress_ticket = "progress_ticket"


class ConditionType(StrEnum):
    is_active = "is_active"
    own = "own"


class PluginType(StrEnum):
    hook = "hook"
    api = "api"


class EventListenTime(StrEnum):
    before = "before"
    after = "after"


class QueryType(StrEnum):
    search = "search"
    subpath = "subpath"
    events = "events"
    history = "history"
    tags = "tags"
    random = "random"
    spaces = "spaces"
    counters = "counters"
    reports = "reports"


class SortType(StrEnum):
    ascending = "ascending"
    descending = "descending"


class Status(StrEnum):
    success = "success"
    failed = "failed"
