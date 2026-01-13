import frappe

def update_agents():
    # 1. OwlAI Analytics
    try:
        agent = frappe.get_doc("OwlAI Agent", "OwlAI Analytics")
        current_tools = [r.tool for r in agent.tools]
        
        if "frappe_utils" not in current_tools:
            agent.append("tools", {"tool": "frappe_utils", "enabled": 1})
            agent.save()
            frappe.db.commit()
            print("Added 'frappe_utils' to OwlAI Analytics")
        else:
            print("'frappe_utils' already in OwlAI Analytics")
    except frappe.DoesNotExistError:
        print("OwlAI Analytics agent not found")

    # 2. OwlAI Navigator
    try:
        agent = frappe.get_doc("OwlAI Agent", "OwlAI Navigator")
        current_tools = [r.tool for r in agent.tools]
        
        if "navigate" not in current_tools:
            agent.append("tools", {"tool": "navigate", "enabled": 1})
            agent.save()
            frappe.db.commit()
            print("Added 'navigate' to OwlAI Navigator")
        else:
            print("'navigate' already in OwlAI Navigator")
    except frappe.DoesNotExistError:
        print("OwlAI Navigator agent not found")

    # 3. OwlAI Assistant (Main)
    try:
        agent = frappe.get_doc("OwlAI Agent", "OwlAI Assistant")
        current_tools = [r.tool for r in agent.tools]
        
        if "frappe_utils" not in current_tools:
            agent.append("tools", {"tool": "frappe_utils", "enabled": 1})
            agent.save()
            frappe.db.commit()
            print("Added 'frappe_utils' to OwlAI Assistant")
        else:
             print("'frappe_utils' already in OwlAI Assistant")
    except frappe.DoesNotExistError:
        print("OwlAI Assistant agent not found")
