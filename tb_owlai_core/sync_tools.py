import frappe
from tb_owlai_core.tool_registry import ToolRegistry

def sync():
    print("Syncing tools...")
    registry = ToolRegistry()
    print("Tools synced successfully.")
    
    # Verify Sync
    print("\n--- Synced Tools ---")
    tools = frappe.get_all("OwlAI Tool", fields=["name", "tool_name", "args_schema"])
    for t in tools:
        print(f"- {t.tool_name}")
