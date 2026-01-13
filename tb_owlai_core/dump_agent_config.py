import frappe
import json

def check():
    try:
        agents = frappe.get_all("OwlAI Agent", fields=["name", "agent_name", "system_prompt", "model"])
        for agent in agents:
            print(f"\n--- Agent: {agent.agent_name} ---")
            print(f"Model: {agent.model}")
            
            # Get child table tools
            tools = frappe.get_all("OwlAI Agent Tool", filters={"parent": agent.name, "enabled": 1}, fields=["tool"])
            tool_names = [t.tool for t in tools]
            print(f"Tools: {tool_names}")
            
            print(f"Prompt: {agent.system_prompt[:200]}..." if agent.system_prompt else "Prompt: <None>")
            
    except Exception as e:
        print(f"Error: {e}")
