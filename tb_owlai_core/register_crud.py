# tb_owlai_core/register_fraud_crud.py
import frappe
import json
from tb_owlai_core.plugins.core.tools.frappe_crud import FrappeCRUDTool

def execute():
    # 1. Register Tool
    tool = FrappeCRUDTool()
    tool_name = tool.name
    schema = tool.args_schema.model_json_schema()
    
    if not frappe.db.exists("OwlAI Tool", tool_name):
        doc = frappe.get_doc({
            "doctype": "OwlAI Tool",
            "tool_name": tool_name,
            "type": "Python Method",
            "method_path": f"ToolRegistry.execute('{tool_name}')",
            "args_schema": json.dumps(schema, indent=2),
            "tool_description": tool.description
        })
        doc.insert(ignore_permissions=True)
        print(f"Created tool '{tool_name}'")
    else:
        # Update
        doc = frappe.get_doc("OwlAI Tool", tool_name)
        doc.args_schema = json.dumps(schema, indent=2)
        doc.save()
        print(f"Updated tool '{tool_name}'")
        
    frappe.db.commit()
    
    # 2. Assign to Agent
    agent_name = "OwlAI Assistant"
    try:
        agent = frappe.get_doc("OwlAI Agent", agent_name)
        current_tools = [t.tool for t in agent.tools]
        if tool_name not in current_tools:
            agent.append("tools", {"tool": tool_name, "enabled": 1})
            agent.save()
            print(f"Assigned '{tool_name}' to '{agent_name}'")
        frappe.db.commit()
    except Exception as e:
        print(f"Failed to assign tool: {e}")
