import frappe
import importlib
import os
import threading
from tb_owlai_core.plugins.base import BasePlugin

# Global lock for thread safety
_plugin_lock = threading.RLock()

class PluginManager:

    def __init__(self):
        self.plugins = {} # map: plugin_name -> plugin_instance
        self.tools = {}   # map: tool_name -> tool_instance
        self.plugin_status = {} # map: plugin_name -> bool (enabled/disabled)

        self.logger = frappe.logger("owlai_plugin_manager")
        self._discover_plugins()
        self._load_enabled_plugins()

    def _discover_plugins(self):
        """
        Scans the 'plugins' directory for valid plugin modules.
        Expected structure: tb_owlai_core/plugins/<name>/plugin.py
        """
        self.plugins = {}
        # Path to plugins directory
        apps_path = frappe.get_app_path("tb_owlai_core", "plugins")
        if not os.path.exists(apps_path):
            return

        for name in os.listdir(apps_path):
            if name.startswith("__") or name.startswith("."):
                continue

            plugin_dir = os.path.join(apps_path, name)
            if not os.path.isdir(plugin_dir):
                continue

            if not os.path.exists(os.path.join(plugin_dir, "plugin.py")):
                continue

            try:
                # Import the module dynamically
                module_path = f"tb_owlai_core.plugins.{name}.plugin"
                module = importlib.import_module(module_path)

                # Find the subclass of BasePlugin
                plugin_class = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                        plugin_class = attr
                        break

                if plugin_class:
                    plugin_instance = plugin_class(self)
                    info = plugin_instance.get_info()
                    plugin_name = info.get("name", name)
                    self.plugins[plugin_name] = plugin_instance
                    # Default status logic
                    # 1. Always enabled flags from plugin info
                    if info.get("always_enabled", False):
                        self.plugin_status[plugin_name] = True
                    else:
                        # 2. Check settings (Future: Load from DB)
                        # For Zero-Config: Default to TRUE if not explicitly disabled
                        # This ensures new users get tools immediately.
                        self.plugin_status[plugin_name] = True

            except Exception as e:
                self.logger.error(f"Failed to load plugin {name}: {str(e)}")

    def _load_enabled_plugins(self):
        """Loads tools from all enabled plugins"""
        self.tools = {}
        for name, plugin in self.plugins.items():
            if self.plugin_status.get(name, False):
                self._load_tools_from_plugin(name, plugin)

    def _load_tools_from_plugin(self, plugin_name, plugin):
        """Loads tools for a specific plugin"""
        tool_names = plugin.get_tools()
        if not tool_names:
            return

        # Convention: Tools are in sibling 'tools' directory or submodule
        # But for list_of_strings, we assume they are modules in 'plugins.<name>.tools.<tool_name>'

        for tool_module_name in tool_names:
            try:
                # Construct import path: tb_owlai_core.plugins.<plugin_name>.tools.<tool_module_name>
                # Note: tool_names in get_tools() should be filenames without .py
                module_path = f"tb_owlai_core.plugins.{plugin_name}.tools.{tool_module_name}"
                module = importlib.import_module(module_path)

                # Verify we can find a BaseTool subclass
                from tb_owlai_core.plugins.base import BaseTool
                tool_instance = None

                # Try simple convention: Class name allows camelcase of file name
                # e.g. create_document -> CreateDocument
                # Or just iterate classes
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BaseTool) and attr is not BaseTool:
                        tool_instance = attr()
                        break

                if tool_instance:
                    # Update tool metadata
                    self.tools[tool_instance.name] = tool_instance
                    self.logger.info(f"Loaded tool: {tool_instance.name} from {plugin_name}")

            except Exception as e:
                self.logger.error(f"Error loading tool {tool_module_name} in {plugin_name}: {str(e)}")

    def get_tool(self, tool_name):
        return self.tools.get(tool_name)

    def get_all_tools(self):
        return list(self.tools.values())

    def refresh_plugins(self):
        """Force rediscovery"""
        with _plugin_lock:
            self._discover_plugins()
            self._load_enabled_plugins()


def get_plugin_manager():
    if not hasattr(frappe.local, '_owlai_plugin_manager'):
        frappe.local._owlai_plugin_manager = PluginManager()
    return frappe.local._owlai_plugin_manager
