import frappe
import json
from tb_owlai_core.agno_integrations.main import get_agent

def test():
    frappe.connect()
    try:
        agent = get_agent()
        print("Agent initialized successfully")
        # dummy run
        # response = agent.run("Hello")
        # print("Response content:", response.content)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
