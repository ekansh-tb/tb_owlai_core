
import frappe
from tb_owlai_core.owlai_core.agent import OwlAgent
from tb_owlai_core.utils.context import OwlContext

def verify_agents():
    print("--- Verifying OwlAI Navigator ---")
    # Simulate Context
    context = OwlContext(route="app/todo")
    
    # Instantiate with specific agent_id
    agent = OwlAgent(user=frappe.session.user, context=context, agent_id="OwlAI Navigator")
    
    print("Query: Go to Task List")
    response = agent.run("Go to Task List")
    print(f"Response: {response}")
    
    print("\n--- Verifying OwlAI Analytics ---")
    agent = OwlAgent(user=frappe.session.user, context=context, agent_id="OwlAI Analytics")

    print("Query: Count all ToDo items")
    response = agent.run("Count all ToDo items")
    print(f"Response: {response}")

if __name__ == "__main__":
    verify_agents()
