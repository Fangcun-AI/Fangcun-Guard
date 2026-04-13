"""
Plugin lifecycle manager — handles discovery, initialization, routing, and shutdown.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from plugins.loader import PluginLoader
from plugins.registry import plugin_registry
from utils.logger import setup_logger

logger = setup_logger()

# Default plugin directories (relative to backend/)
DEFAULT_BUILTIN_DIR = Path(__file__).parent.parent / "plugins_builtin"
DEFAULT_CUSTOM_DIR = Path(__file__).parent.parent / "plugins_custom"


class PluginManager:
    """Manages plugin lifecycle: load -> initialize -> register routes -> shutdown"""

    def __init__(self):
        self._initialized = False
        self._discovered = False

    def discover_and_register(
        self,
        builtin_dir: Optional[Path] = None,
        custom_dir: Optional[Path] = None,
    ) -> int:
        """
        Synchronous plugin discovery and registration (no async calls).
        Call this at module import time to make plugins and their routers available.

        Returns:
            Number of discovered plugins
        """
        if self._discovered:
            return plugin_registry.plugin_count

        builtin_dir = builtin_dir or DEFAULT_BUILTIN_DIR
        custom_dir = custom_dir or DEFAULT_CUSTOM_DIR

        search_dirs = [builtin_dir, custom_dir]
        discovered = PluginLoader.discover_plugins(search_dirs)

        if not discovered:
            logger.info("No plugins discovered")
            self._discovered = True
            return 0

        logger.info(f"Discovered {len(discovered)} plugin(s): {', '.join(n for n, _ in discovered)}")

        count = 0
        for name, plugin in discovered:
            try:
                plugin_registry.register(name, plugin)
                count += 1
            except Exception as e:
                logger.error(f"Failed to register plugin '{name}': {e}")

        self._discovered = True
        return count

    async def initialize_all(self, app_context: Optional[Dict[str, Any]] = None) -> None:
        """
        Async initialization of all registered plugins.
        Call this inside lifespan or startup event.
        """
        if self._initialized:
            return

        app_context = app_context or {}
        for name, plugin in list(plugin_registry.get_all().items()):
            try:
                await plugin.initialize(app_context)
            except Exception as e:
                logger.error(f"Failed to initialize plugin '{name}': {e}")
                plugin_registry.unregister(name)

        self._initialized = True
        logger.info(f"Plugin system initialized: {plugin_registry.plugin_count} plugin(s) active")

    async def load_and_initialize(
        self,
        app=None,
        builtin_dir: Optional[Path] = None,
        custom_dir: Optional[Path] = None,
        app_context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Discover, register, initialize all plugins, and register their routes.

        Args:
            app: FastAPI application instance (for registering routes)
            builtin_dir: Path to built-in plugins directory
            custom_dir: Path to custom plugins directory
            app_context: Context passed to plugin.initialize()

        Returns:
            Number of successfully loaded plugins
        """
        if self._initialized:
            logger.warning("PluginManager already initialized, skipping")
            return plugin_registry.plugin_count

        builtin_dir = builtin_dir or DEFAULT_BUILTIN_DIR
        custom_dir = custom_dir or DEFAULT_CUSTOM_DIR
        app_context = app_context or {}

        # Discover plugins
        search_dirs = [builtin_dir, custom_dir]
        discovered = PluginLoader.discover_plugins(search_dirs)

        if not discovered:
            logger.info("No plugins discovered")
            self._initialized = True
            return 0

        logger.info(f"Discovered {len(discovered)} plugin(s): {', '.join(n for n, _ in discovered)}")

        # Register and initialize
        loaded_count = 0
        for name, plugin in discovered:
            try:
                plugin_registry.register(name, plugin)
                await plugin.initialize(app_context)

                # Register routes if app is provided
                if app is not None:
                    for router in plugin.get_routers():
                        app.include_router(router)
                        logger.info(f"Registered routes for plugin: {name}")

                loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to initialize plugin '{name}': {e}")
                plugin_registry.unregister(name)

        self._initialized = True
        logger.info(f"Plugin system initialized: {loaded_count} plugin(s) active")
        return loaded_count

    async def shutdown_all(self) -> None:
        """Shutdown all plugins gracefully"""
        for name, plugin in plugin_registry.get_all().items():
            try:
                await plugin.shutdown()
                logger.info(f"Plugin '{name}' shut down")
            except Exception as e:
                logger.error(f"Plugin '{name}' shutdown error: {e}")

        self._initialized = False
        logger.info("Plugin system shut down")

    def run_plugin_migrations(self) -> None:
        """Run database migrations for all registered plugins"""
        from plugins.migration_runner import run_plugin_migrations as _run
        _run(plugin_registry.get_all())


# Global singleton
plugin_manager = PluginManager()
