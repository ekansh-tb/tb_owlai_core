import frappe
from tb_owlai_core.utils.plugin_manager import PluginManager

class ToolRegistry:
    """
    Facade for accessing tools managed by PluginManager.
    Keeps API clean and similar to previous architecture requests.
    """
    
    def __init__(self):
        self.plugin_manager = PluginManager()
        self._sync_tools()

    def _sync_tools(self):
        """
        Syncs available tools from PluginManager to 'OwlAI Tool' DocType.
        Ensures all plugin-discovered tools are registered in the system.
        """
        import json
        available_tools = self.plugin_manager.get_all_tools()
        
        for tool in available_tools:
            if not frappe.db.exists("OwlAI Tool", {"tool_name": tool.name}):
                try:
                    tool_doc = frappe.get_doc({
                        "doctype": "OwlAI Tool",
                        "tool_name": tool.name,
                        "type": "Python Method",
                        "args_schema": json.dumps(tool.inputSchema, indent=2),
                        "enable_cache": 0,
                        # We leverage the registry to execute, so method_path might not be strictly needed 
                        # for the standard execution flow, but we can store the class name or module.
                        "method_path": f"ToolRegistry.execute('{tool.name}')" 
                    })
                    tool_doc.insert(ignore_permissions=True)
                    frappe.db.commit()
                except Exception as e:
                    frappe.logger("owlai").error(f"Failed to sync tool {tool.name}: {str(e)}")

    def get_tool(self, tool_name):
        """
        Get a specific tool instance by name.
        """
        return self.plugin_manager.get_tool(tool_name)

    def get_available_tools(self):
        """
        Get list of all available tools as dicts for LLM system prompt.
        """
        tools = self.plugin_manager.get_all_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
                "category": tool.category
            }
            for tool in tools
        ]

    def get_tools_schema(self):
        """
        Alias for get_available_tools to match Agent expectations.
        """
        return self.get_available_tools()

    def execute_tool(self, tool_name, arguments):
        """
        Execute a tool safely.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found."
            
        return tool._safe_execute(arguments)

    def execute(self, tool_name, arguments):
        """
        Alias for execute_tool to match Agent usage.
        """
        return self.execute_tool(tool_name, arguments)
