import pytest
from models.enums import (
    StrEnum,
    RequestType,
    Language,
    PublicSubmitResourceType,
    ResourceType,
    DataAssetType,
    AttachmentType,
    ContentType,
    TaskType,
    UserType,
    ValidationEnum,
    LockAction,
    NotificationType,
    NotificationPriority,
    StrBoolEnum,
    ActionType,
    ConditionType,
    PluginType,
    EventListenTime,
    QueryType,
    SortType,
    Status,
    RedisReducerName,
    ReactionType,
)
import redis.commands.search.reducers as reducers


def test_str_enum():
    class TestEnum(StrEnum):
        test = "test"

    assert str(TestEnum.test) == "test"


def test_request_type():
    assert RequestType.create == "create"
    assert RequestType.update == "update"


def test_language():
    assert Language.ar == "arabic"
    assert Language.code("english") == "en"
    with pytest.raises(KeyError):
        Language.code("nonexistent")


def test_resource_type():
    assert ResourceType.user == "user"
    assert ResourceType.folder == "folder"


def test_data_asset_type():
    assert DataAssetType.csv == "csv"
    assert DataAssetType.parquet == "parquet"


def test_attachment_type():
    assert AttachmentType.comment == "comment"
    assert AttachmentType.lock == "lock"


def test_content_type():
    assert ContentType.text == "text"
    assert ContentType.inline_types() == [ContentType.text, ContentType.markdown, ContentType.html]


def test_task_type():
    assert TaskType.query == "query"


def test_user_type():
    assert UserType.web == "web"
    assert UserType.bot == "bot"


def test_validation_enum():
    assert ValidationEnum.valid == "valid"
    assert ValidationEnum.invalid == "invalid"


def test_lock_action():
    assert LockAction.lock == "lock"
    assert LockAction.extend == "extend"


def test_notification_type():
    assert NotificationType.admin == "admin"
    assert NotificationType.system == "system"


def test_notification_priority():
    assert NotificationPriority.high == "high"
    assert NotificationPriority.medium == "medium"


def test_str_bool_enum():
    assert StrBoolEnum.true == "yes"
    assert StrBoolEnum.false == "no"


def test_action_type():
    assert ActionType.query == "query"
    assert ActionType.view == "view"


def test_condition_type():
    assert ConditionType.is_active == "is_active"
    assert ConditionType.own == "own"


def test_plugin_type():
    assert PluginType.hook == "hook"
    assert PluginType.api == "api"


def test_event_listen_time():
    assert EventListenTime.before == "before"
    assert EventListenTime.after == "after"


def test_query_type():
    assert QueryType.search == "search"
    assert QueryType.events == "events"


def test_sort_type():
    assert SortType.ascending == "ascending"
    assert SortType.descending == "descending"


def test_status():
    assert Status.success == "success"
    assert Status.failed == "failed"


def test_redis_reducer_name():
    assert RedisReducerName.count_distinct == "count_distinct"
    assert RedisReducerName.mapper("r_count") == reducers.count
    with pytest.raises(KeyError):
        RedisReducerName.mapper("nonexistent")


def test_reaction_type():
    assert ReactionType.like == "like"
    assert ReactionType.care == "care"


def test_public_submit_resource_type():
    assert PublicSubmitResourceType.content == "content"
    assert PublicSubmitResourceType.ticket == "ticket"


def test_content_type_missing():
    """ContentType._missing_ should map 'image' to image_jpeg."""
    assert ContentType("image") == ContentType.image_jpeg
    assert ContentType("json") == ContentType.json
    # Non-existent value should raise ValueError
    with pytest.raises(ValueError):
        ContentType("nonexistent_type")


def test_content_type_image_types():
    """ContentType.image_types() should return the set of image content types."""
    image_types = ContentType.image_types()
    assert ContentType.image_jpeg in image_types
    assert ContentType.image_png in image_types
    assert ContentType.image_svg in image_types
    assert ContentType.image_gif in image_types
    assert ContentType.image_webp in image_types
    assert len(image_types) == 5
    # Non-image types should not be in the set
    assert ContentType.json not in image_types
    assert ContentType.text not in image_types
