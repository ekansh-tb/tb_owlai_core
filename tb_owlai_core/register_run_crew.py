import frappe
import json

def execute():
    # 1. Create or Update 'Run Crew' Tool
    tool_name = "Run Crew"
    method_path = "tb_owlai_core.owlai_core.doctype.owlai_crew.owlai_crew.run_crew"
    schema = {
        "type": "object",
        "properties": {
            "crew_name": {
                "type": "string",
                "description": "The name of the Crew to run."
            }
        },
        "required": ["crew_name"]
    }
    
    if not frappe.db.exists("OwlAI Tool", tool_name):
        doc = frappe.get_doc({
            "doctype": "OwlAI Tool",
            "tool_name": tool_name,
            "type": "Python Method",
            "method_path": method_path,
            "args_schema": json.dumps(schema, indent=2),
            "tool_description": "Executes a CrewAI crew by its name."
        })
        doc.insert(ignore_permissions=True)
        print(f"Created tool '{tool_name}'")
    else:
        doc = frappe.get_doc("OwlAI Tool", tool_name)
        doc.method_path = method_path
        doc.args_schema = json.dumps(schema, indent=2)
        doc.save(ignore_permissions=True)
        print(f"Updated tool '{tool_name}'")
        
    frappe.db.commit()
    
    # 2. Assign to 'OwlAI Assistant'
    agent_name = "OwlAI Assistant"
    if frappe.db.exists("OwlAI Agent", agent_name):
        agent = frappe.get_doc("OwlAI Agent", agent_name)
        
        # Check if already assigned (by checking child table)
        exists = False
        for t in agent.tools:
            if t.tool == tool_name: # Field in child table is 'tool'
                # Wait, child table 'OwlAI Agent Tool' has field 'tool' usually.
                # Let's check OwlAI Agent structure again.
                # In Step 32 (OwlAI Tool), the name is "OwlAI Tool". 
                # In Step 31 (OwlAI Agent), fields -> tools -> options "OwlAI Agent Tool".
                # I need to check "OwlAI Agent Tool" schema to know the field name. 
                # Usually it's a Link to "OwlAI Tool".
                # I'll blindly guess 'tool' or 'tool_name'.
                # Let's check Update Agent Tools script (Step 68). 
                # It uses: agent.append("tools", {"tool": "frappe_utils", "enabled": 1})
                # So the field name is "tool".
                pass
        
        # We need to iterate again safely
        current_tools = [t.tool for t in agent.tools]
        if tool_name not in current_tools:
            agent.append("tools", {
                "tool": tool_name,
                "enabled": 1
            })
            agent.save(ignore_permissions=True)
            print(f"Assigned '{tool_name}' to '{agent_name}'")
        else:
            print(f"'{tool_name}' already assigned to '{agent_name}'")
            
        frappe.db.commit()
    else:
        print(f"Agent '{agent_name}' not found. Please create it first.")

