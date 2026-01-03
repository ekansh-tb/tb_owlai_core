import frappe
from tb_owlai_core.utils.plugin_manager import PluginManager

class ToolRegistry:
    """
    Facade for accessing tools managed by PluginManager.
    Keeps API clean and similar to previous architecture requests.
    """
    
    def __init__(self):
        self.plugin_manager = PluginManager()

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

    def execute_tool(self, tool_name, arguments):
        """
        Execute a tool safely.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found."
            
        return tool._safe_execute(arguments)
