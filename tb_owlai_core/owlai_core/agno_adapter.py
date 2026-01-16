from typing import List, Any
from agno.tools import Toolkit
from tb_owlai_core.tool_registry import ToolRegistry
import frappe

class OwlAIToolkit(Toolkit):
    def __init__(self, tool_names: List[str], result_callback=None):
        super().__init__(name="owl_toolkit")
        self.registry = ToolRegistry()
        self.result_callback = result_callback
        
        for name in tool_names:
            self._register_tool_by_name(name)

    def _register_tool_by_name(self, name: str):
        # We need the actual Tool class instance
        # ToolRegistry.get_tool_doc gives the Doc, PluginManager gives the instance
        tool = self.registry.plugin_manager.get_tool(name)
        
        if not tool:
            frappe.logger("owlai").warning(f"OwlAIToolkit: Tool '{name}' not found in PluginManager.")
            return

        # 1. Get Pydantic Schema
        Schema = tool.args_schema
        if not Schema:
            # Fallback for tools without schema? (Should not happen after refactor)
            return

        # 2. Create Wrapper Function
        # We use a closure to capture 'tool' and 'Schema'
        def wrapper(args: Schema):
            try:
                # Convert Pydantic model to dict
                params = args.model_dump()
                # Execute tool
                result = tool.execute(params)
                
                # Capture result if callback provided
                if self.result_callback:
                    self.result_callback(tool.name, params, result)
                    
                return result
            except Exception as e:
                return f"Error executing {tool.name}: {str(e)}"
        
        # 3. Set Function Metadata
        wrapper.__name__ = tool.name
        wrapper.__doc__ = tool.description
        
        # 4. Register with Toolkit
        self.register(wrapper)
