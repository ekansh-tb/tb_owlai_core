
import frappe
from tb_owlai_core.api.router import handle_input_v2
import json

def test_create_and_navigate():
    # Simulate a request that triggers create_document
    # We'll mock the agent or just call the tool directly to verify the side-channel
    
    # 1. Test CreateDocument Tool direct execution
    from tb_owlai_core.plugins.core.tools.create_document import CreateDocument
    tool = CreateDocument()
    
    # Create a dummy Note (safe doctype)
    args = {
        "doctype": "Note",
        "data": {"title": "Test Note for Navigation", "public": 1},
        "submit": False
    }
    
    print("Executing CreateDocument tool directly...")
    frappe.local.owlai_actions = [] # clear
    result = tool.execute(args)
    
    print(f"Tool Result: {json.dumps(result, indent=2)}")
    print(f"Side Channel: {json.dumps(frappe.local.owlai_actions, indent=2)}")
    
    if "docname" in result and result.get("action") == "navigate":
        print("✅ CreateDocument returns navigation action.")
    else:
        print("❌ CreateDocument missing navigation action.")

    if frappe.local.owlai_actions and frappe.local.owlai_actions[0].get("action") == "navigate":
        print("✅ CreateDocument populated owlai_actions.")
    else:
        print("❌ CreateDocument failed to populate owlai_actions.")

    # Clean up
    if "name" in result:
        frappe.delete_doc("Note", result["name"])

if __name__ == "__main__":
    try:
        frappe.connect("mp_v1") # Adjust site if needed, likely owlnest.localhost based on context but standard bench commands handle site
        test_create_and_navigate()
    except Exception as e:
        print(e)
