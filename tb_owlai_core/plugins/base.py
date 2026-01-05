import frappe
import json
import time
from abc import ABC, abstractmethod
from typing import Optional, Type, Dict, Any, List, Tuple
from pydantic import BaseModel, ValidationError

class BaseTool(ABC):
    """
    Abstract base class for all OwlAI tools.
    Enhanced with validation, permission checks, and robust execution logging.
    """
    args_schema: Optional[Type[BaseModel]] = None

    def __init__(self):
        self.name = "unnamed_tool"
        self.description = "No description provided"
        # Default empty schema, will be overridden by args_schema if present
        self._input_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        self.requires_permission: Optional[str] = None # DocType permission required e.g. "Sales Order"
        self.category = "Generic"
        self.source_app = "tb_owlai_core"
        self.dependencies: List[str] = []
        self.default_config: Dict[str, Any] = {}
        self.logger = frappe.logger(self.__class__.__module__)

    @property
    def inputSchema(self) -> Dict[str, Any]:
        """
        Returns JSON schema for the tool. Use Pydantic schema if available.
        """
        if self.args_schema:
            return self.args_schema.model_json_schema()
        return self._input_schema

    @inputSchema.setter
    def inputSchema(self, value):
        self._input_schema = value

    @abstractmethod
    def execute(self, arguments: Dict[str, Any]) -> Any:
        """
        Execute the tool with the given arguments.
        Must return a serializable result (dict, list, str, etc.)
        """
        pass

    def check_permission(self) -> None:
        """
        Check if current user has required permissions.
        """
        if self.requires_permission:
            # Check read permission on the DocType
            if not frappe.has_permission(self.requires_permission, "read"):
                frappe.throw(
                    f"Insufficient permissions to execute {self.name}. Required: {self.requires_permission}",
                    frappe.PermissionError
                )

    def validate_dependencies(self) -> Tuple[bool, Optional[str]]:
        """
        Check if all tool dependencies are available.
        """
        if not self.dependencies:
            return True, None

        missing_deps = []
        for dep in self.dependencies:
            try:
                __import__(dep)
            except ImportError:
                missing_deps.append(dep)

        if missing_deps:
            return False, f"Missing dependencies: {', '.join(missing_deps)}"

        return True, None

    def _safe_execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safely execute tool with error handling, timing, and logging.
        """
        start_time = time.time()
        
        try:
            # 1. Dependency Check
            deps_valid, deps_error = self.validate_dependencies()
            if not deps_valid:
                return {"success": False, "error": deps_error, "error_type": "DependencyError"}

            # 2. Permission Check
            self.check_permission()

            # 3. Argument Validation & Parsing
            cleaned_args = arguments
            if self.args_schema:
                try:
                    # Validate and convert using Pydantic
                    model_instance = self.args_schema(**arguments)
                    cleaned_args = model_instance.model_dump()
                except ValidationError as ve:
                    # Provide clear error message
                    return {
                        "success": False, 
                        "error": f"Invalid Arguments: {ve.errors()}", 
                        "error_type": "ValidationError"
                    }

            # 4. Execute
            result = self.execute(cleaned_args)
            execution_time = time.time() - start_time

            # Log Success (Info level)
            self.logger.info(f"Tool {self.name} executed in {execution_time:.3f}s")
            
            return {
                "success": True, 
                "result": result, 
                "execution_time": execution_time
            }

        except frappe.PermissionError as e:
            execution_time = time.time() - start_time
            self.logger.warning(f"Permission denied for {self.name}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "PermissionError",
                "execution_time": execution_time
            }

        except Exception as e:
            execution_time = time.time() - start_time
            # Detailed error logging
            import traceback
            trace = traceback.format_exc()
            
            error_msg = f"Tool {self.name} failed: {str(e)}"
            self.logger.error(error_msg)
            frappe.log_error(title=f"OwlAI Tool Error: {self.name}", message=f"{error_msg}\n\nArgs: {arguments}\n\n{trace}")

            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time": execution_time
            }

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
