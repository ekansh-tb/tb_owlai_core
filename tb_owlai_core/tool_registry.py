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
        Ensures all plugin-discovered tools are registered and updated in the system.
        """
        import json
        available_tools = self.plugin_manager.get_all_tools()
        
        for tool in available_tools:
            new_schema = json.dumps(tool.inputSchema, indent=2)
            
            if frappe.db.exists("OwlAI Tool", {"tool_name": tool.name}):
                # Update existing tool if schema changed
                try:
                    tool_doc = frappe.get_doc("OwlAI Tool", {"tool_name": tool.name})
                    current_schema = tool_doc.args_schema
                    
                    # Normalize for comparison
                    if current_schema != new_schema:
                        tool_doc.args_schema = new_schema
                        tool_doc.method_path = f"ToolRegistry.execute('{tool.name}')" # Ensure path is correct
                        tool_doc.save(ignore_permissions=True)
                        frappe.db.commit()
                        frappe.logger("owlai").info(f"Updated schema for tool {tool.name}")
                except Exception as e:
                    frappe.logger("owlai").error(f"Failed to update tool {tool.name}: {str(e)}")
            else:
                # Create new tool
                try:
                    tool_doc = frappe.get_doc({
                        "doctype": "OwlAI Tool",
                        "tool_name": tool.name,
                        "type": "Python Method",
                        "args_schema": new_schema,
                        "enable_cache": 0,
                        "method_path": f"ToolRegistry.execute('{tool.name}')" 
                    })
                    tool_doc.insert(ignore_permissions=True)
                    frappe.db.commit()
                    frappe.logger("owlai").info(f"Created new tool {tool.name}")
                except Exception as e:
                    frappe.logger("owlai").error(f"Failed to sync tool {tool.name}: {str(e)}")

    def get_tool_doc(self, tool_name):
        if frappe.db.exists("OwlAI Tool", {"tool_name": tool_name}):
            return frappe.get_doc("OwlAI Tool", {"tool_name": tool_name})
        return None

    def get_tools_schema(self):
        """
        Get schemas from OwlAI Tool database records.
        """
        tools_docs = frappe.get_all("OwlAI Tool", fields=["tool_name", "args_schema"])
        schemas = []
        for t in tools_docs:
            if t.args_schema:
                try:
                    import json
                    schema = json.loads(t.args_schema)
                    # Ensure name matches (sometimes schema name might differ in auto-gen)
                    schema["name"] = t.tool_name
                    schemas.append(schema)
                except:
                    pass
        return schemas

    def execute_tool(self, tool_name, arguments):
        """
        Execute a tool safely using DB definition or Plugin fallback.
        """
        tool_doc = self.get_tool_doc(tool_name)
        
        if not tool_doc:
            # Fallback to direct plugin lookup (Legacy/Unsynced)
            tool = self.plugin_manager.get_tool(tool_name)
            if tool:
                return tool._safe_execute(arguments)
            return f"Error: Tool '{tool_name}' not found."

        # 1. Handle Python Method (Direct Call)
        if tool_doc.type == "Python Method" and tool_doc.method_path:
            # Check if it's a Plugin Proxy (synced from code)
            if "ToolRegistry.execute" in tool_doc.method_path:
                 # It's a plugin tool, use manager
                 tool = self.plugin_manager.get_tool(tool_name)
                 if tool:
                     return tool._safe_execute(arguments)
                 return f"Error: Underlying Plugin for '{tool_name}' not found."
            
            # Real Dotted Path Execution
            try:
                # Security: You might want to restrict this to whitelisted methods or specific allowed paths
                # usage: frappe.client.get_list -> frappe.call("frappe.client.get_list", ...)
                return frappe.call(tool_doc.method_path, **arguments)
            except Exception as e:
                frappe.log_error(f"Tool Execution Error: {tool_name}")
                return f"Error executing {tool_name}: {str(e)}"
        
        return f"Error: Tool Type '{tool_doc.type}' execution not implemented."

    def execute(self, tool_name, arguments):
        """
        Alias for execute_tool to match Agent usage.
        """
        return self.execute_tool(tool_name, arguments)
