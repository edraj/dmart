import asyncio
import os
import sys
import time
from importlib.util import find_spec, module_from_spec
from inspect import iscoroutine
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import Depends, FastAPI
from fastapi.logger import logger

from models import api
from models.core import (
    ActionType,
    Event,
    EventFilter,
    EventListenTime,
    PluginBase,
    PluginWrapper,
)
from models.enums import PluginType, ResourceType
from utils.settings import settings

CUSTOM_PLUGINS_PATH = settings.spaces_folder / "custom_plugins"

_background_tasks: set[asyncio.Task] = set()

# Allow python to search for modules inside the custom plugins
# by including the path to the parent folder of the custom plugins to sys.path
if CUSTOM_PLUGINS_PATH.parent.exists():
    sys.path.append(str(CUSTOM_PLUGINS_PATH.parent.resolve()))


class PluginManager:
    plugins_wrappers: dict[ActionType, list[PluginWrapper]] = {}  # {action_type: list_of_plugins_wrappers]}

    active_plugins: list[str] = []

    # Short-lived cache for space lookups to avoid redundant Redis calls
    # within the same request (before_action + after_action both fetch the same space)
    _space_cache: dict[str, tuple[float, Any]] = {}
    _SPACE_CACHE_TTL: float = 2.0  # seconds

    @classmethod
    async def _get_space_cached(cls, space_name: str) -> Any:
        """Fetch space with a short TTL cache to avoid double-loading within a single request."""
        now = time.monotonic()
        cached = cls._space_cache.get(space_name)
        if cached is not None:
            ts, space = cached
            if now - ts < cls._SPACE_CACHE_TTL:
                return space

        from data_adapters.adapter import data_adapter as db

        space = await db.fetch_space(space_name)
        cls._space_cache[space_name] = (now, space)
        return space

    async def load_plugins(self, app: FastAPI, capture_body):
        # Load core plugins
        current = Path(__file__).resolve().parent
        parent = current.parent
        path = parent / "plugins"
        if path.is_dir():
            await self.load_path_plugins(path, app, capture_body)

        # Load custom plugins
        path = CUSTOM_PLUGINS_PATH
        if path.is_dir():
            await self.load_path_plugins(path, app, capture_body)
        self.sort_plugins()

    async def load_path_plugins(self, path: Path, app: FastAPI, capture_body):

        plugins_iterator = os.scandir(path)
        for plugin_path in plugins_iterator:
            config_file_path = Path(f"{plugin_path.path}/config.json")
            plugin_file_path = Path(f"{plugin_path.path}/plugin.py")
            if not config_file_path.is_file() or not plugin_file_path.is_file():
                continue

            # Load plugin config file
            async with aiofiles.open(config_file_path) as config_file:
                plugin_wrapper: PluginWrapper = PluginWrapper.model_validate_json(await config_file.read())
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
                    plugin_wrapper.object = module.Plugin()

                    self.store_plugin_in_its_action_dict(plugin_wrapper)

                self.active_plugins.append(plugin_wrapper.shortname)
                print(f"PLUGIN_LOADED: {plugin_wrapper.shortname}")
                logger.info(f"PLUGIN_LOADED: {plugin_wrapper.shortname}")
            except Exception as e:
                logger.error(f"PLUGIN_ERROR, PLUGIN API {plugin_wrapper.shortname} Failed to load, error: {e.args}")

        plugins_iterator.close()

    def store_plugin_in_its_action_dict(self, plugin_wrapper: PluginWrapper):
        if plugin_wrapper.filters:
            for action in plugin_wrapper.filters.actions:
                self.plugins_wrappers.setdefault(action, []).append(plugin_wrapper)

    def sort_plugins(self):
        """Sort plugins based on plugin_wrapper.ordinal"""

        for action_type, plugins in self.plugins_wrappers.items():
            self.plugins_wrappers[action_type] = sorted(plugins, key=lambda x: x.ordinal)

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
            "__ALL__" not in plugin_filters.schema_shortnames and event.schema_shortname not in plugin_filters.schema_shortnames
        ):
            return False

        return not (
            plugin_filters.resource_types
            and "__ALL__" not in plugin_filters.resource_types
            and event.resource_type not in plugin_filters.resource_types
        )

    async def _safe_coroutine_execution(self, coro, plugin_model):
        try:
            await coro
        except api.Exception as e:
            logger.error(f"Plugin:{plugin_model} raised api.Exception: {e!s}")
        except Exception as e:
            logger.error(f"Plugin:{plugin_model}:{e!s}")

    async def before_action(self, event: Event):
        if event.action_type not in self.plugins_wrappers:
            return

        # Short-circuit: check if any plugin for this action listens to 'before'
        plugins = self.plugins_wrappers[event.action_type]
        before_plugins = [p for p in plugins if p.listen_time == EventListenTime.before and p.filters]
        if not before_plugins:
            return

        space = await self._get_space_cached(event.space_name)
        if space is None:
            return
        space_plugins = space.active_plugins

        for plugin_model in before_plugins:
            if (
                plugin_model.shortname in space_plugins
                and plugin_model.filters is not None
                and self.matched_filters(plugin_model.filters, event)
            ):
                try:
                    object = plugin_model.object
                    if isinstance(object, PluginBase):
                        plugin_execution = object.hook(event)
                        if iscoroutine(plugin_execution):
                            await plugin_execution
                except api.Exception as e:
                    raise e
                except Exception as e:
                    logger.error(f"Plugin:{plugin_model}:{e!s}")

    async def after_action(self, event: Event):
        if event.action_type not in self.plugins_wrappers:
            return

        # Short-circuit: check if any plugin for this action listens to 'after'
        plugins = self.plugins_wrappers[event.action_type]
        after_plugins = [p for p in plugins if p.listen_time == EventListenTime.after and p.filters]
        if not after_plugins:
            return

        space = await self._get_space_cached(event.space_name)
        if space is None:
            return
        space_plugins = space.active_plugins

        loop = asyncio.get_running_loop()
        for plugin_model in after_plugins:
            if (
                plugin_model.shortname in space_plugins
                and plugin_model.filters is not None
                and self.matched_filters(plugin_model.filters, event)
            ):
                try:
                    object = plugin_model.object
                    if isinstance(object, PluginBase):
                        plugin_execution = object.hook(event)
                        if iscoroutine(plugin_execution):
                            if plugin_model.concurrent:
                                task = loop.create_task(self._safe_coroutine_execution(plugin_execution, plugin_model))
                                _background_tasks.add(task)
                                task.add_done_callback(_background_tasks.discard)
                            else:
                                await plugin_execution
                except api.Exception as e:
                    raise e
                except Exception as e:
                    logger.error(f"Plugin:{plugin_model}:{e!s}")


plugin_manager = PluginManager()
