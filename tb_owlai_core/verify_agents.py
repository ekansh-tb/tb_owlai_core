
import frappe
from tb_owlai_core.owlai_core.agent import OwlAgent
from tb_owlai_core.utils.context import OwlContext

def verify_agents():
    print("--- Verifying OwlAI Navigator ---")
    nav_agent_doc = frappe.get_doc("OwlAI Agent", {"agent_name": "OwlAI Navigator"})
    # Simulate Context
    context = OwlContext(route="app/todo")
    agent = OwlAgent(user=frappe.session.user, context=context)
    # Override configuration to use Navigator
    agent.agent_doc = nav_agent_doc
    agent.config["system_prompt"] = nav_agent_doc.system_prompt
    agent.config["tools"] = agent._get_allowed_tools() # Reload tools for this agent

    # Test Query
    print("Query: Go to Task List")
    response = agent.run("Go to Task List")
    print(f"Response: {response}")
    
    print("\n--- Verifying OwlAI Analytics ---")
    anal_agent_doc = frappe.get_doc("OwlAI Agent", {"agent_name": "OwlAI Analytics"})
    agent = OwlAgent(user=frappe.session.user, context=context)
    agent.agent_doc = anal_agent_doc
    agent.config["system_prompt"] = anal_agent_doc.system_prompt
    agent.config["tools"] = agent._get_allowed_tools()

    print("Query: Count all ToDo items")
    response = agent.run("Count all ToDo items")
    print(f"Response: {response}")

if __name__ == "__main__":
    verify_agents()
