
import frappe

def setup_specialized_agents():
    """
    Creates specialized agents: Navigator and Analytics.
    """
    # 1. Navigator Agent
    if not frappe.db.exists("OwlAI Agent", {"agent_name": "OwlAI Navigator"}):
        # Tools: navigate, search_documents, get_doctype_info
        tools = []
        for t in ["navigate", "search_documents", "get_doctype_info", "list_documents"]:
            if frappe.db.exists("OwlAI Tool", {"tool_name": t}):
                tools.append({"tool": frappe.db.get_value("OwlAI Tool", {"tool_name": t}, "name"), "enabled": 1})

        doc = frappe.get_doc({
            "doctype": "OwlAI Agent",
            "agent_name": "OwlAI Navigator",
            "system_prompt": """You are the OwlAI Navigator. Your ONLY purpose is to help the user navigate to the right page in Frappe/ERPNext.
Core Rules:
1. If the user asks for a list (e.g., "Show me Tasks"), use `navigate` with view='List'.
2. If the user asks for a specific document (e.g., "Open Task 001"), use `navigate` to the Form.
3. If you can't find the DocType, use `search_documents` to find it.
4. Be brief. Just navigate.""",
            "model": _get_default_model(),
            "tools": tools
        })
        doc.insert(ignore_permissions=True)
        print("Created OwlAI Navigator")
    else:
        # Update existing
        name = frappe.db.get_value("OwlAI Agent", {"agent_name": "OwlAI Navigator"}, "name")
        doc = frappe.get_doc("OwlAI Agent", name)
        
        # Tools: navigate, search_documents, get_doctype_info
        tools = []
        for t in ["navigate", "search_documents", "get_doctype_info", "list_documents"]:
            if frappe.db.exists("OwlAI Tool", {"tool_name": t}):
                tool_id = frappe.db.get_value("OwlAI Tool", {"tool_name": t}, "name")
                tools.append({"tool": tool_id, "enabled": 1})
        
        # Clear and re-add to ensure order and presence
        doc.tools = []
        doc.extend("tools", tools)
        doc.save(ignore_permissions=True)
        print("Updated OwlAI Navigator")

    # 2. Analytics Agent
    if not frappe.db.exists("OwlAI Agent", {"agent_name": "OwlAI Analytics"}):
        # Tools: list_documents, generate_report, get_doctype_info, frappe_utils
        tools = []
        for t in ["list_documents", "generate_report", "get_doctype_info", "frappe_utils", "get_page_content"]:
             if frappe.db.exists("OwlAI Tool", {"tool_name": t}):
                tools.append({"tool": frappe.db.get_value("OwlAI Tool", {"tool_name": t}, "name"), "enabled": 1})
        
        doc = frappe.get_doc({
            "doctype": "OwlAI Agent",
            "agent_name": "OwlAI Analytics",
            "system_prompt": """You are the OwlAI Data Analyst. You help users understand their data.
Core Rules:
1. Use `list_documents` to fetch raw data. 
2. Use `frappe_utils` for formatting.
3. Summarize data effectively. If the result is too large, ask the user to refine filter.
4. NEVER modify data. You are read-only.""",
            "model": _get_default_model(),
            "tools": tools
        })
        doc.insert(ignore_permissions=True)
        print("Created OwlAI Analytics")
    else:
        # Update existing
        name = frappe.db.get_value("OwlAI Agent", {"agent_name": "OwlAI Analytics"}, "name")
        doc = frappe.get_doc("OwlAI Agent", name)
        
        # Tools: list_documents, generate_report, get_doctype_info, frappe_utils
        tools = []
        for t in ["list_documents", "generate_report", "get_doctype_info", "frappe_utils", "get_page_content"]:
             if frappe.db.exists("OwlAI Tool", {"tool_name": t}):
                tool_id = frappe.db.get_value("OwlAI Tool", {"tool_name": t}, "name")
                tools.append({"tool": tool_id, "enabled": 1})
        
        doc.tools = []
        doc.extend("tools", tools)
        doc.save(ignore_permissions=True)
        print("Updated OwlAI Analytics")

    frappe.db.commit()

def _get_default_model():
    # Use same model as default assistant
    settings = frappe.get_single("OwlAI Settings")
    default_agent = settings.default_agent
    if default_agent:
        return frappe.db.get_value("OwlAI Agent", default_agent, "model")
    return None
