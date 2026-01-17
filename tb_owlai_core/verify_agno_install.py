
import frappe
from tb_owlai_core.agno_integrations.main import get_agent

def test_agno_agent():
    print("--- Testing OwlAi Agent Integration ---")
    
    # 1. Create a dummy conversation
    conv = frappe.new_doc("OwlAI Conversation")
    conv.title = "Agno Verification Test"
    conv.save(ignore_permissions=True)
    print(f"Created Conversation: {conv.name}")
    
    # 2. Instantiate Agent
    try:
        agent = get_agent(conversation_id=conv.name)
        print(f"Agent Instantiated: {agent.model.id}")
        
        # 3. Run Query
        print("Running Query: 'What is the current time?'")
        response = agent.print_response("What is the current time?", stream=False)
        # Note: print_response prints to stdout, but we also want the return value if possible.
        # agent.run() returns a RunResponse
        
        print("\nRunning Query: 'List all ToDo items'")
        # This checks Tool Usage
        resp_obj = agent.run("List 3 ToDo items")
        print(f"Response Object: {resp_obj}")
        print(f"Response Content: {resp_obj.content}")
        
        # 4. Verify Persistence
        conv.reload()
        print(f"\nStored Messages in DB: {len(conv.messages)}")
        for m in conv.messages:
            print(f"- [{m.role}] {m.content[:50]}...")
            
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_agno_agent()
