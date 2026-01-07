from enum import StrEnum
import redis.commands.search.reducers as reducers


class RequestType(StrEnum):
    create = "create"
    update = "update"
    patch = "patch"
    update_acl = "update_acl"
    assign = "assign"
    delete = "delete"
    move = "move"


class Language(StrEnum):
    ar = "arabic"
    en = "english"
    ku = "kurdish"
    fr = "french"
    tr = "turkish"

    @staticmethod
    def code(lang_str):
        codes = {
            "arabic": "ar",
            "english": "en",
            "kurdish": "ku",
            "french": "fr",
            "turkish": "tr",
        }
        return codes[lang_str]


class PublicSubmitResourceType(StrEnum):
    content = "content"
    ticket = "ticket"


class ResourceType(StrEnum):
    user = "user"
    group = "group"
    folder = "folder"
    schema = "schema"
    content = "content"
    log = "log"
    acl = "acl"
    comment = "comment"
    media = "media"
    data_asset = "data_asset"
    locator = "locator"
    relationship = "relationship"
    alteration = "alteration"
    history = "history"
    space = "space"
    permission = "permission"
    role = "role"
    ticket = "ticket"
    json = "json"
    lock = "lock"
    post = "post"
    reaction = "reaction"
    reply = "reply"
    share = "share"
    plugin_wrapper = "plugin_wrapper"
    notification = "notification"
    csv = "csv"
    jsonl = "jsonl"
    sqlite = "sqlite"
    duckdb = "duckdb"
    parquet = "parquet"


class DataAssetType(StrEnum):
    csv = "csv"
    jsonl = "jsonl"
    sqlite = "sqlite"
    duckdb = "duckdb"
    parquet = "parquet"


class AttachmentType(StrEnum):
    reaction = "reaction"
    share = "share"
    json = "json"
    reply = "reply"
    comment = "comment"
    lock = "lock"
    media = "media"
    data_asset = "data_asset"
    relationship = "relationship"
    alteration = "alteration"


class ContentType(StrEnum):
    text = "text"
    comment = "comment"
    reaction = "reaction"
    markdown = "markdown"
    html = "html"
    json = "json"
    image = "image"
    python = "python"
    pdf = "pdf"
    audio = "audio"
    video = "video"
    csv = "csv"
    parquet = "parquet"
    jsonl = "jsonl"
    apk = "apk"
    duckdb = "duckdb"
    sqlite = "sqlite"

    @staticmethod
    def inline_types() -> list:
        return [ContentType.text, ContentType.markdown, ContentType.html]


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
    fetch = "fetch"
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
    assign = "assign"
    move = "move"
    progress_ticket = "progress_ticket"
    lock = "lock"
    unlock = "unlock"


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
    aggregation = "aggregation"
    attachments = "attachments"
    attachments_aggregation = "attachments_aggregation"


class SortType(StrEnum):
    ascending = "ascending"
    descending = "descending"


class Status(StrEnum):
    success = "success"
    failed = "failed"


class RedisReducerName(StrEnum):
    count_distinct = "count_distinct"
    r_count = "r_count"
    # Same as COUNT_DISTINCT - but provide an approximation instead of an exact count,
    # at the expense of less memory and CPU in big groups
    count_distinctish = "count_distinctish"
    sum = "sum"
    min = "min"
    max = "max"
    avg = "avg"
    # Returns all the matched properties in a list
    tolist = "tolist"
    quantile = "quantile"
    stddev = "stddev"
    # Selects the first value within the group according to sorting parameters
    first_value = "first_value"
    # Returns a random sample of items from the dataset, from the given property
    random_sample = "random_sample"

    @staticmethod
    def mapper(red: str):
        map = {
            "r_count": reducers.count,
            "count_distinct": reducers.count_distinct,
            "count_distinctish": reducers.count_distinctish,
            "sum": reducers.sum,
            "min": reducers.min,
            "max": reducers.max,
            "avg": reducers.avg,
            "tolist": reducers.tolist,
            "quantile": reducers.quantile,
            "stddev": reducers.stddev,
            "first_value": reducers.first_value,
            "random_sample": reducers.random_sample,
        }
        return map[red]


class ReactionType(StrEnum):
    like = "like"
    dislike = "dislike"
    love = "love"
    care = "care"
    laughing = "laughing"
    sad = "sad"
