
import frappe

def setup_agents():
    """
    Creates default OwlAI Agents and Tools for testing Phase 3 features.
    """
    print("Setting up Agents...")
    

    # 1. Create Tools if missing
    tools = [
        {"name": "Web Search", "method": "DuckDuckGo", "type": "Python Method"},
        {"name": "Frappe Toolkit", "method": "FrappeToolkit", "type": "Python Method"}
    ]
    
    for t in tools:
        if not frappe.db.exists("OwlAI Tool", {"tool_name": t["name"]}):
            new_tool = frappe.new_doc("OwlAI Tool")
            new_tool.tool_name = t["name"]
            new_tool.type = t["type"]
            # method_path is optional for native tools handled in main.py
            new_tool.save(ignore_permissions=True)
            print(f"Created Tool: {t['name']}")

    

    # 2. Get Model
    models = frappe.get_list("OwlAI Model", limit=1)
    if not models:
        # Create a default model if missing
        if not frappe.db.exists("OwlAI Model", {"name": "Llama 3"}):
            model = frappe.new_doc("OwlAI Model")
            model.model_name = "Llama 3"
            model.provider = "Ollama" 
            # Assuming provider exists or free text
            model.save(ignore_permissions=True)
            model_name = model.name
        else:
            model_name = "Llama 3"
    else:
        model_name = models[0].name


    # 3. Create Research Agent
    if not frappe.db.exists("OwlAI Agent", {"agent_name": "Research Agent"}):
        agent = frappe.new_doc("OwlAI Agent")
        agent.agent_name = "Research Agent"
        agent.role = "System Manager" # Must be a valid Role
        agent.system_prompt = "You are a research assistant. Use the Web Search tool to find information."
        agent.model = model_name
        
        # Add Web Search Tool
        tool_doc_name = frappe.db.get_value("OwlAI Tool", {"tool_name": "Web Search"}, "name")
        if tool_doc_name:
            agent.append("tools", {"tool": tool_doc_name, "enabled": 1})
        
        agent.save(ignore_permissions=True)
        print("Created Agent: Research Agent")
        
    # 4. Create Actionable Agent
    if not frappe.db.exists("OwlAI Agent", {"agent_name": "Actionable Agent"}):
        agent = frappe.new_doc("OwlAI Agent")
        agent.agent_name = "Actionable Agent"
        agent.role = "System Manager"
        agent.system_prompt = "You are an actionable agent. You can navigate, creates documents, and answer questions about the system."

        agent.model = model_name
        
        # Add Frappe Toolkit
        tool_doc_name = frappe.db.get_value("OwlAI Tool", {"tool_name": "Frappe Toolkit"}, "name")
        if tool_doc_name:
            agent.append("tools", {"tool": tool_doc_name, "enabled": 1})
        
        agent.save(ignore_permissions=True)
        print("Created Agent: Actionable Agent")


    frappe.db.commit()
    print("Agent Setup Complete.")

if __name__ == "__main__":
    setup_agents()
