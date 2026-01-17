
import frappe

def fix_actionable_agent():
    agent_name = "Actionable Agent"
    if not frappe.db.exists("OwlAI Agent", {"agent_name": agent_name}):
        print(f"Agent {agent_name} not found.")
        return

    doc = frappe.get_doc("OwlAI Agent", {"agent_name": agent_name})
    
    # List of tools to enable
    tools_to_enable = [
        "navigate",
        "frappe_utils",
        "get_page_content",
        "list_documents",
        "search_documents",
        "get_doctype_info",
        "web_search" # Assuming "Web Search" tool is named "web_search" or "Web Search"?
    ]

    # Check actual tool names in DB
    # force_register_tools.py registers "Web Search" with name "Web Search" or "web_search"? 
    # It uses `d.tool_name = name` where name is "Web Search". So it's "Web Search".
    # But for others it uses `tool.name`. 
    
    # Let's handle both cases/ensure we get the right ones.
    
    final_tools = []
    
    # Map of preferred alias to possible DB names
    target_tools = {
        "navigate": ["navigate"],
        "frappe_utils": ["frappe_utils"],
        "get_page_content": ["get_page_content"],
        "list_documents": ["list_documents"],
        "search_documents": ["search_documents"],
        "get_doctype_info": ["get_doctype_info"],
        "web_search": ["Web Search", "web_search"]
    }

    print(f"Updating tools for {agent_name}...")
    
    for key, possibilities in target_tools.items():
        found = False
        for tool_name in possibilities:
            if frappe.db.exists("OwlAI Tool", {"tool_name": tool_name}):
                tool_doc_name = frappe.db.get_value("OwlAI Tool", {"tool_name": tool_name}, "name")
                final_tools.append({"tool": tool_doc_name, "enabled": 1})
                print(f"  Added tool: {tool_name}")
                found = True
                break
        if not found:
            print(f"  Warning: Tool '{key}' not found in DB.")

    doc.tools = []
    doc.extend("tools", final_tools)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"Successfully updated {agent_name} with {len(final_tools)} tools.")

if __name__ == "__main__":
    fix_actionable_agent()
