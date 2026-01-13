
import frappe
import json

def execute():
    print("--- OwlAI Settings ---")
    try:
        settings = frappe.get_single("OwlAI Settings")
        print(json.dumps(settings.as_dict(), indent=2, default=str))
    except Exception as e:
        print(f"Error fetching settings: {e}")

    print("\n--- OwlAI Agents ---")
    try:
        agents = frappe.get_all("OwlAI Agent", fields=["name", "agent_name", "model", "system_prompt"])
        print(json.dumps(agents, indent=2, default=str))
        
        # Check details of first agent
        if agents:
            first_agent = frappe.get_doc("OwlAI Agent", agents[0].name)
            print(f"\nDetails for Agent: {first_agent.agent_name}")
            print("Tools:", [t.tool for t in first_agent.tools])
    except Exception as e:
        print(f"Error fetching agents: {e}")

    print("\n--- OwlAI Tools ---")
    try:
        tools = frappe.get_all("OwlAI Tool", fields=["name", "tool_name", "type", "method_path"])
        print(json.dumps(tools, indent=2, default=str))
    except Exception as e:
        print(f"Error fetching tools: {e}")

    print("\n--- Recent OwlAI Runs (Last 5) ---")
    try:
        runs = frappe.get_all("OwlAI Run", fields=["name", "status", "start_time", "duration", "error_message"], order_by="start_time desc", limit=5)
        print(json.dumps(runs, indent=2, default=str))
    except Exception as e:
        print(f"Error fetching runs: {e}")

    print("\n--- OwlAI Analytics Stats ---")
    try:
        count = frappe.db.count("OwlAI Analytics")
        print(f"Total Analytics Records: {count}")
    except Exception as e:
        print(f"Error fetching analytics: {e}")
