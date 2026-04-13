"""
Plugin registry — singleton that manages all registered plugins.
"""

import threading
from typing import Dict, List, Optional, Any
from plugins.base import FangcunPlugin, DetectionPlugin
from plugins.hooks import HookPhase, HookContext, HookResult
from utils.logger import setup_logger

logger = setup_logger()


class PluginRegistry:
    """Singleton plugin registry"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._plugins: Dict[str, FangcunPlugin] = {}
        return cls._instance

    def register(self, name: str, plugin: FangcunPlugin) -> None:
        """Register a plugin by name"""
        with self._lock:
            if name in self._plugins:
                logger.warning(f"Plugin '{name}' is already registered, overwriting")
            self._plugins[name] = plugin
            logger.info(f"Registered plugin: {name} (v{plugin.get_metadata().version})")

    def unregister(self, name: str) -> None:
        """Unregister a plugin by name"""
        with self._lock:
            if name in self._plugins:
                del self._plugins[name]
                logger.info(f"Unregistered plugin: {name}")

    def get(self, name: str) -> Optional[FangcunPlugin]:
        """Get a plugin by name"""
        return self._plugins.get(name)

    def get_all(self) -> Dict[str, FangcunPlugin]:
        """Get all registered plugins"""
        return dict(self._plugins)

    def get_detection_plugins(self) -> List[DetectionPlugin]:
        """Get all detection plugins, sorted by priority (lower number = higher priority)"""
        detection_plugins = [
            p for p in self._plugins.values()
            if isinstance(p, DetectionPlugin)
        ]
        detection_plugins.sort(key=lambda p: p.get_metadata().priority)
        return detection_plugins

    async def dispatch_hook(self, phase: HookPhase, ctx: HookContext) -> List[HookResult]:
        """
        Dispatch a hook to all detection plugins and collect results.
        Plugins are called in priority order.
        """
        results = []
        detection_plugins = self.get_detection_plugins()

        for plugin in detection_plugins:
            try:
                handler = {
                    HookPhase.INPUT: plugin.on_input_check,
                    HookPhase.OUTPUT: plugin.on_output_check,
                    HookPhase.DETECTION: plugin.on_detection_check,
                    HookPhase.STREAM_COMPLETE: plugin.on_stream_complete,
                }.get(phase)

                if handler is None:
                    continue

                result = await handler(ctx)
                if result is not None:
                    result.plugin_name = plugin.get_metadata().name
                    results.append(result)
                    # Update existing results so later plugins can reference earlier ones
                    ctx.existing_results[result.plugin_name] = {
                        "risk_level": result.risk_level,
                        "categories": result.categories,
                        "action": result.action,
                        "metadata": result.metadata,
                    }
            except Exception as e:
                plugin_name = plugin.get_metadata().name
                logger.error(f"Plugin '{plugin_name}' hook '{phase.value}' failed: {e}")

        return results

    @property
    def plugin_count(self) -> int:
        return len(self._plugins)

    @property
    def plugin_names(self) -> List[str]:
        return list(self._plugins.keys())


# Global singleton instance
plugin_registry = PluginRegistry()
