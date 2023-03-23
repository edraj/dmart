import asyncio
from inspect import iscoroutine
import os
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import Depends, FastAPI
from models.core import (
    ActionType,
    PluginWrapper,
    PluginBase,
    Event,
    EventFilter,
    EventListenTime,
    Space,
)
from models.enums import ResourceType, PluginType
from utils.settings import settings
from utils.spaces import get_spaces
from importlib.util import find_spec, module_from_spec
import sys
from fastapi.logger import logger


# Allow python to search for modules inside the custom plugins
# be including the path to the parent folder of the custom plugins to sys.path
back_out_of_project = 2
back_to_spaces = 0
for part in settings.custom_plugins_path.parts:
    if part == "..":
        back_to_spaces += 1

sys.path.append(
    "/".join(__file__.split("/")[:-(back_out_of_project+back_to_spaces)]) + 
    "/" + 
    "/".join(settings.custom_plugins_path.parts[back_to_spaces:-1])
)

class PluginManager:

    plugins_wrappers: dict[
        ActionType, list[PluginWrapper]
    ] = {}  # {action_type: list_of_plugins_wrappers]}

    async def load_plugins(self, app: FastAPI, capture_body):
        # Load core plugins
        path = Path("plugins")
        if path.is_dir():
            await self.load_path_plugins(path, app, capture_body)

        # Load custom plugins
        path = settings.custom_plugins_path
        if path.is_dir():
            await self.load_path_plugins(path, app, capture_body)
        self.sort_plugins()


    async def load_path_plugins(self, path: Path, app: FastAPI, capture_body):

        plugins_iterator = os.scandir(path)
        for plugin_path in plugins_iterator:
            config_file_path = Path(f"{plugin_path.path}/config.json")
            plugin_file_path = Path(f"{plugin_path.path}/plugin.py")
            if(
                not config_file_path.is_file() or
                not plugin_file_path.is_file()
            ):
                continue

            # Load plugin config file
            async with aiofiles.open(config_file_path, "r") as config_file:
                plugin_wrapper: PluginWrapper = PluginWrapper.parse_raw(
                    await config_file.read()
                )
            plugin_wrapper.shortname = plugin_path.name
            if not plugin_wrapper.is_active:
                continue
            # Load the plugin module
            module_name = f"{path.parts[-1]}.{plugin_wrapper.shortname}.plugin"
            spec = find_spec(module_name)
            if not spec:
                continue
            module = module_from_spec(spec)
            sys.modules[module_name] = module
            if not spec.loader:
                continue
            spec.loader.exec_module(module)
            try:
                # Register the API plugin routes
                if plugin_wrapper.type == PluginType.api:
                    app.include_router(
                        module.router,
                        prefix=f"/{plugin_wrapper.shortname}",
                        tags=[plugin_wrapper.shortname],
                        dependencies=[Depends(capture_body)],
                    )

                # Add the Hook Plugin to the loaded plugins
                elif plugin_wrapper.type == PluginType.hook:
                    plugin_wrapper.object = getattr(module, "Plugin")()

                    self.store_plugin_in_its_action_dict(plugin_wrapper)
            except Exception as e:
                logger.error(
                    f"PLUGIN_ERROR, PLUGIN API {plugin_wrapper.shortname} Failed to load, error: {e.args}"
                )

        plugins_iterator.close()

    def store_plugin_in_its_action_dict(self, plugin_wrapper: PluginWrapper):
        if plugin_wrapper.filters:
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
                and plugin_model.filters
                and self.matched_filters(plugin_model.filters, event)
            ):
                try:
                    object = plugin_model.object
                    if isinstance(object, PluginBase):
                        plugin_execution = object.hook(event)
                        if iscoroutine(plugin_execution):
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
                and plugin_model.filters
                and self.matched_filters(plugin_model.filters, event)
            ):
                try:
                    object = plugin_model.object
                    if isinstance(object, PluginBase):
                        plugin_execution = object.hook(event)
                        if iscoroutine(plugin_execution):
                            loop.create_task(plugin_execution)
                except Exception as e:
                    logger.error(f"Plugin:{plugin_model}:{str(e)}")


plugin_manager = PluginManager()
