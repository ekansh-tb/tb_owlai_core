import frappe
def check():
    agents = frappe.get_all("OwlAI Agent", fields=["name", "agent_name"])
    print("Agents found:", agents)

check()
