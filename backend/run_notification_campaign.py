import argparse
import asyncio
from importlib.util import find_spec, module_from_spec
import sys

from models.core import Content, Event
from models.enums import ActionType
from data_adapters.adapter import data_adapter as db
from utils.settings import settings

CUSTOM_PLUGINS_PATH = settings.spaces_folder / "custom_plugins"

# Allow python to search for modules inside the custom plugins
# by including the path to the parent folder of the custom plugins to sys.path
if CUSTOM_PLUGINS_PATH.parent.exists():
    sys.path.append(str(CUSTOM_PLUGINS_PATH.parent.resolve()))

def load_notification_plugin():
    # Load the plugin module
    plugin_path = CUSTOM_PLUGINS_PATH / 'send_notification'
    
    config_file_path = plugin_path / 'config.json'
    plugin_file_path = plugin_path / 'plugin.py'
    if(
        not config_file_path.is_file() or
        not plugin_file_path.is_file()
    ):
        return None


    module_name = f"{CUSTOM_PLUGINS_PATH.parts[-1]}.send_notification.plugin"
    spec = find_spec(module_name)
    if not spec:
        return None
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    return getattr(module, "Plugin")()
    
    
async def main(space, subpath, shortname):
    notification_payload = db.load_resource_payload(
        space_name=space,
        subpath=subpath,
        class_type=Content,
        filename=f"{shortname}.json",
    )
    
    if not notification_payload:
        print("The notification entry is not found")
        return
    
    event_data = Event(
        space_name=space,
        subpath=subpath,
        shortname=shortname,
        action_type=ActionType.create,
        attributes={
            "payload": {
                "body": notification_payload
            }
        },
        user_shortname="__SYSTEM__"
    )
    
    
    plugin_obj = load_notification_plugin()
    if not plugin_obj:
        print("The plugin is not found")
        return
    
    await plugin_obj.hook(event_data)
    
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Execute the custom_plugins/send_notification plugin",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--space", help="The space where the notification request and user records are stored")
    parser.add_argument("--notification-subpath", help="The subpath of the notification request")
    parser.add_argument("--notification-shortname", help="The shortname of the notification request")

    args = parser.parse_args()

    asyncio.run(main(args.space, args.notification_subpath, args.notification_shortname))
