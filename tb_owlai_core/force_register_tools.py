
import frappe
import json
# Import the tool classes directly
from tb_owlai_core.plugins.core.tools.navigate import NavigateTool
from tb_owlai_core.plugins.core.tools.frappe_utils import FrappeUtilsTool
from tb_owlai_core.plugins.core.tools.context_tools import GetPageContentTool

def force_register():
    print("Force Registering Tools...")
    
    tools_to_register = [
        NavigateTool(),
        FrappeUtilsTool(),
        GetPageContentTool()
    ]
    
    for tool in tools_to_register:
        print(f"Registering {tool.name}...")
        
        # 1. Create/Update OwlAI Tool Record
        tool_doc_name = tool.name
        if frappe.db.exists("OwlAI Tool", {"tool_name": tool.name}):
            tool_doc_name = frappe.db.get_value("OwlAI Tool", {"tool_name": tool.name}, "name")
            doc = frappe.get_doc("OwlAI Tool", tool_doc_name)
        else:
            doc = frappe.new_doc("OwlAI Tool")
            doc.tool_name = tool.name
            doc.name = tool.name # Try to set name if possible or let autobbox handle if standard
        
        doc.type = "Python Method" # Core tools are registered as methods routed via Registry
        doc.method_path = f"ToolRegistry.execute('{tool.name}')"
        doc.description = tool.description
        doc.json_schema = json.dumps(tool.inputSchema, indent=2)
        doc.enabled = 1
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"Saved OwlAI Tool: {doc.name}")

    # 2. Re-run Agent Setup to Link these tools
    from tb_owlai_core.setup.setup_agents import setup_specialized_agents
    setup_specialized_agents()
    print("Refreshed Agents.")

if __name__ == "__main__":
    force_register()
