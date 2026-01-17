
import frappe
import json
# Import the tool classes directly
from tb_owlai_core.plugins.core.tools.navigate import NavigateTool
from tb_owlai_core.plugins.core.tools.frappe_utils import FrappeUtilsTool
from tb_owlai_core.plugins.core.tools.context_tools import GetPageContentTool
from tb_owlai_core.plugins.core.tools.list_documents import ListDocuments
from tb_owlai_core.plugins.core.tools.search_documents import SearchDocuments
from tb_owlai_core.plugins.core.tools.get_doctype_info import GetDoctypeInfo

def force_register():
    print("Force Registering Tools...")
    
    tools_to_register = [
        NavigateTool(),
        FrappeUtilsTool(),
        GetPageContentTool(),
        ListDocuments(),
        SearchDocuments(),
        GetDoctypeInfo()
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
        doc.args_schema = json.dumps(tool.inputSchema, indent=2)
        doc.enabled = 1
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"Saved OwlAI Tool: {doc.name}")

    # 2. Re-run Agent Setup to Link these tools
    from tb_owlai_core.setup.setup_agents import setup_specialized_agents
    setup_specialized_agents()
    print("Refreshed Agents.")

    # 3. Register Toolkits (Placeholders/Containers)
    toolkits = [
        {
            "name": "Frappe Toolkit", 
            "description": "Comprehensive toolkit for Frappe/ERPNext interactions including Navigation, CRUD operations, and Search.",
            "tool_name": "Frappe Toolkit"
        },
        {
            "name": "Web Search", 
            "description": "Search the internet for real-time information using DuckDuckGo.",
            "tool_name": "Web Search"
        }
    ]

    for tk in toolkits:
        name = tk["name"]
        print(f"Registering Toolkit {name}...")
        
        doc_name = name
        if frappe.db.exists("OwlAI Tool", {"tool_name": name}):
             doc_name = frappe.db.get_value("OwlAI Tool", {"tool_name": name}, "name")
             d = frappe.get_doc("OwlAI Tool", doc_name)
        elif frappe.db.exists("OwlAI Tool", name):
             d = frappe.get_doc("OwlAI Tool", name)
        else:
             d = frappe.new_doc("OwlAI Tool")
             d.tool_name = name
             d.name = name
        
        d.type = "Python Method"
        d.description = tk["description"]
        
        # Ensure schema is valid JSON object, even if empty
        if not d.args_schema or d.args_schema == "null":
            d.args_schema = "{}"
            
        d.enabled = 1
        d.save(ignore_permissions=True)
        frappe.db.commit()
        print(f"Saved Toolkit: {d.name}")

if __name__ == "__main__":
    force_register()
