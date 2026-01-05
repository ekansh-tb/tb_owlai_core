import frappe
from abc import ABC, abstractmethod
import json

from typing import Optional, Type, Dict, Any
from pydantic import BaseModel, ValidationError

class BaseTool(ABC):
    """
    Abstract base class for all OwlAI tools.
    """
    args_schema: Optional[Type[BaseModel]] = None

    def __init__(self):
        self.name = "unnamed_tool"
        self.description = "No description provided"
        self._input_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        self.requires_permission = None # Optional: "read", "write", "create", etc.
        self.category = "Uncategorized"

    @property
    def inputSchema(self):
        if self.args_schema:
            return self.args_schema.model_json_schema()
        return self._input_schema

    @inputSchema.setter
    def inputSchema(self, value):
        self._input_schema = value

    @abstractmethod
    def execute(self, arguments):
        """
        Execute the tool with the given arguments.
        Must return a serializable result (dict, list, str, etc.)
        """
        pass

    def _safe_execute(self, arguments):
        """
        Wrapper to handle validation, permissions, and error logging.
        """
        try:
            # 1. Permission check (basic)
            if self.requires_permission and frappe.session.user != "Administrator":
                # This is a placeholder. Real implementations might check specifically against a doctype
                pass 

            # 2. Validation
            cleaned_args = arguments
            if self.args_schema:
                try:
                    # Validate and convert to model, then back to dict for execute
                    # This ensures parsing/types are correct
                    model_instance = self.args_schema(**arguments)
                    cleaned_args = model_instance.model_dump()
                except ValidationError as ve:
                     return f"Tool Argument Error: {ve.errors()}"

            # 3. Execute
            return self.execute(cleaned_args)
        except Exception as e:
            frappe.log_error(f"OwlAI Tool Error ({self.name})", str(e))
            return f"Error executing tool '{self.name}': {str(e)}" 

class BasePlugin(ABC):
    """
    Abstract base class for all OwlAI plugins.
    """
    def __init__(self, manager):
        self.manager = manager
        self.logger = frappe.logger("owlai_plugin")

    @abstractmethod
    def get_info(self):
        """
        Return metadata about the plugin.
        Dict with keys: name, display_name, description, version, dependencies, requires_restart
        """
        pass

    @abstractmethod
    def get_tools(self):
        """
        Return a list of tool *module names* (strings) relative to the plugin's tool directory,
        OR a list of instantiated Tool classes if dynamically generated.
        Currently supporting module names for auto-loading.
        """
        pass

    def validate_environment(self):
        """
        Optional: Check if external dependencies (API keys, binaries) are present.
        Returns: (bool, error_message)
        """
        return True, None

    def on_enable(self):
        """Called when plugin is enabled"""
        pass

    def on_disable(self):
        """Called when plugin is disabled"""
        pass
    
    def get_capabilities(self):
        """Return a dict of detailed capabilities for frontend/admin UI"""
        return {}
