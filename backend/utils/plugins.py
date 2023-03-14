import asyncio
from inspect import isawaitable
import os
from pathlib import Path
import aiofiles
from models.core import (
    ActionType,
    PluginWrapper,
    Event,
    EventFilter,
    EventListenTime,
    Space,
)
from models.enums import ResourceType
from utils.settings import settings
from utils.spaces import get_spaces
from importlib import import_module
from importlib.util import find_spec, module_from_spec
import sys
from fastapi.logger import logger


# Allow python to search for modules inside "spaces" folder
spaces_ups = 2
for part in settings.spaces_folder.parts:
    if part == "..":
        spaces_ups += 1
sys.path.append(
    "/".join(__file__.split("/")[:-spaces_ups]) + f"/{settings.spaces_folder.name}"
)


class PluginManager:

    plugins_wrappers: dict[
        ActionType, list[PluginWrapper]
    ] = {}  # {action_type: list_of_plugins_wrappers]}

    async def load_plugins(self):
        path = settings.spaces_folder / settings.management_space / "plugins/.dm"
        if not path.is_dir():
            return

        plugins_iterator = os.scandir(path)
        for plugin_path in plugins_iterator:
            meta_file_path = Path(f"{plugin_path.path}/meta.plugin_wrapper.json")
            if not meta_file_path.is_file():
                continue

            async with aiofiles.open(meta_file_path, "r") as meta_file:
                plugin_wrapper = PluginWrapper.parse_raw(await meta_file.read())

            try:
                module_name = f"plugins.{plugin_wrapper.shortname}"
                core_plugin_specs = find_spec(module_name)

                if core_plugin_specs:
                    module = module_from_spec(core_plugin_specs)
                    sys.modules[module_name] = module
                    core_plugin_specs.loader.exec_module(module)  # type: ignore
                    plugin_wrapper.object = module.Plugin()
                else:
                    plugin_wrapper.object = import_module(
                        f"{settings.management_space}.plugins.{plugin_wrapper.shortname}"
                    ).Plugin()  # intialize the class in memory load_plugins

                if plugin_wrapper.is_active:
                    self.store_plugin_in_its_action_dict(plugin_wrapper)

            except Exception as e:
                logger.error(
                    f"PLUGIN_ERROR, Plugin {plugin_wrapper.shortname} Failed to load, error: {e.args}"
                )

        self.sort_plugins()
        plugins_iterator.close()

    def store_plugin_in_its_action_dict(self, plugin_wrapper: PluginWrapper):
        for action in plugin_wrapper.filters.actions:
            self.plugins_wrappers.setdefault(action, []).append(plugin_wrapper)

    def sort_plugins(self):
        """Sort plugins based on plugin_wrapper.ordinal"""

        for action_type, plugins in self.plugins_wrappers.items():
            self.plugins_wrappers[action_type] = sorted(
                plugins, key=lambda x: x.ordinal
            )

    def matched_filters(self, plugin_filters: EventFilter, event: Event):
        formats_of_subpath = [event.subpath]
        if event.subpath and event.subpath[0] == "/":
            formats_of_subpath.append(event.subpath[1:])
        else:
            formats_of_subpath.append(f"/{event.subpath}")

        if "__ALL__" not in plugin_filters.subpaths and not any(
            subpath in plugin_filters.subpaths for subpath in formats_of_subpath
        ):
            return False

        if event.resource_type == ResourceType.content and (
            "__ALL__" not in plugin_filters.schema_shortnames
            and event.schema_shortname not in plugin_filters.schema_shortnames
        ):
            return False

        if (
            plugin_filters.resource_types
            and "__ALL__" not in plugin_filters.resource_types
            and event.resource_type not in plugin_filters.resource_types
        ):
            return False

        return True

    async def before_action(self, event: Event):
        spaces = await get_spaces()
        if (
            event.space_name not in spaces
            or not event.action_type in self.plugins_wrappers
        ):
            return

        space_plugins = Space.parse_raw(spaces[event.space_name]).active_plugins

        loop = asyncio.get_event_loop()
        for plugin_model in self.plugins_wrappers[event.action_type]:
            if (
                plugin_model.shortname in space_plugins
                and plugin_model.listen_time == EventListenTime.before
                and self.matched_filters(plugin_model.filters, event)
            ):
                try:
                    plugin_execution = plugin_model.object.hook(event)  # type: ignore
                    if isawaitable(plugin_execution):
                        loop.create_task(plugin_execution)
                except Exception as e:
                    logger.error(f"Plugin:{plugin_model}:{str(e)}")

    async def after_action(self, event: Event):
        spaces = await get_spaces()
        if (
            event.space_name not in spaces
            or not event.action_type in self.plugins_wrappers
        ):
            return

        space_plugins = Space.parse_raw(spaces[event.space_name]).active_plugins
        loop = asyncio.get_event_loop()
        for plugin_model in self.plugins_wrappers[event.action_type]:
            if (
                plugin_model.shortname in space_plugins
                and plugin_model.listen_time == EventListenTime.after
                and self.matched_filters(plugin_model.filters, event)
            ):
                try:
                    plugin_execution = plugin_model.object.hook(event)  # type: ignore
                    if isawaitable(plugin_execution):
                        loop.create_task(plugin_execution)
                except Exception as e:
                    logger.error(f"Plugin:{plugin_model}:{str(e)}")


plugin_manager = PluginManager()
asyncio.run(plugin_manager.load_plugins())
