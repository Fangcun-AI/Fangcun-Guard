"""
Plugin discovery and dynamic loading via importlib.
"""

import importlib.util
import sys
from pathlib import Path
from typing import List, Tuple, Optional
from plugins.base import FangcunPlugin
from utils.logger import setup_logger

logger = setup_logger()


class PluginLoader:
    """Discovers and loads plugins from directories"""

    @staticmethod
    def discover_plugins(directories: List[Path]) -> List[Tuple[str, FangcunPlugin]]:
        """
        Scan directories for plugin packages (subdirectories with plugin.py containing PluginClass).

        Returns:
            List of (plugin_name, plugin_instance) tuples
        """
        plugins = []

        for directory in directories:
            if not directory.exists():
                logger.debug(f"Plugin directory not found: {directory}")
                continue

            for subdir in sorted(directory.iterdir()):
                if not subdir.is_dir() or subdir.name.startswith(('_', '.')):
                    continue

                plugin_file = subdir / "plugin.py"
                if not plugin_file.exists():
                    continue

                plugin = PluginLoader._load_plugin(subdir.name, plugin_file)
                if plugin is not None:
                    plugins.append((subdir.name, plugin))

        return plugins

    @staticmethod
    def _load_plugin(name: str, plugin_file: Path) -> Optional[FangcunPlugin]:
        """Load a single plugin from its plugin.py file"""
        module_name = f"plugin_{name}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if spec is None or spec.loader is None:
                logger.warning(f"Cannot create module spec for plugin '{name}'")
                return None

            module = importlib.util.module_from_spec(spec)

            # Add the plugin's parent directory to sys.path so it can do relative imports
            plugin_parent = str(plugin_file.parent.parent)
            plugin_dir = str(plugin_file.parent)
            added_paths = []
            for p in [plugin_parent, plugin_dir]:
                if p not in sys.path:
                    sys.path.insert(0, p)
                    added_paths.append(p)

            try:
                spec.loader.exec_module(module)
            finally:
                # Clean up sys.path additions
                for p in added_paths:
                    if p in sys.path:
                        sys.path.remove(p)

            # Look for PluginClass in the module
            plugin_cls = getattr(module, 'PluginClass', None)
            if plugin_cls is None:
                logger.warning(f"Plugin '{name}' has no PluginClass in plugin.py")
                return None

            if not (isinstance(plugin_cls, type) and issubclass(plugin_cls, FangcunPlugin)):
                logger.warning(f"Plugin '{name}' PluginClass does not inherit from FangcunPlugin")
                return None

            instance = plugin_cls()
            logger.info(f"Loaded plugin: {name}")
            return instance

        except Exception as e:
            logger.error(f"Failed to load plugin '{name}': {e}")
            return None
