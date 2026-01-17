
import frappe
import json
from tb_owlai_core.agno_integrations.main import get_agent
from tb_owlai_core.agno_integrations.storage import FrappeStorage
from agno.session import AgentSession
from tb_owlai_core.tool_registry import ToolRegistry
from tb_owlai_core.agno_integrations.tools import FrappeToolkit

def run():
    print("="*60)
    print("🧪 Phase 2: Agent & Tool Functionality Testing (Fixed)")
    print("="*60)

    # 1. Test Agent Factory
    print(f"\n[1] Testing Agent Factory (get_agent):")
    try:
        agent = get_agent(conversation_id="test-phase-2-conv", debug_mode=True)
        print(f"  ✅ Agent Initialized: {agent.model.id if agent.model else 'Unknown Resource'}")
        if agent.tools:
            print(f"  🔹 Tools Loaded: {len(agent.tools)}")
    except Exception as e:
        print(f"  ❌ Agent Factory Failed: {e}")

    # 2. Test FrappeStorage
    print(f"\n[2] Testing FrappeStorage (Session Persistence):")
    try:
        storage = FrappeStorage()
        session_id = "test-phase-2-session-refined"
        
        # Upsert
        session = AgentSession(session_id=session_id, agent_id="test_agent", user_id="Administrator")
        storage.upsert_session(session)
        
        # Verify by session_id field
        if frappe.db.exists("OwlAI Conversation", {"session_id": session_id}):
             print(f"  ✅ Session '{session_id}' persisted to DB.")
        else:
             print(f"  ❌ Session '{session_id}' NOT found in DB!")
             
        # Cleanup
        name = frappe.db.get_value("OwlAI Conversation", {"session_id": session_id}, "name")
        if name:
            frappe.delete_doc("OwlAI Conversation", name, ignore_permissions=True)
            print(f"  ✅ Cleanup: Deleted test session.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  ❌ FrappeStorage Test Failed: {e}")

    # 3. Test Tool Registry & Execution
    print(f"\n[3] Testing Tool Registry & Core Tools:")
    registry = ToolRegistry()
    
    def unwrap(res):
        if isinstance(res, dict) and "success" in res:
            if res["success"]:
                return res["result"]
            else:
                print(f"    ⚠️ Tool Error: {res.get('error')}")
                return None
        return res

    # 3.1 List Documents
    print(f"  🔹 Testing 'list_documents'...")
    try:
        raw = registry.execute("list_documents", {
            "doctype": "User", 
            "limit_page_length": 1,
            "fields": ["email"]
        })
        res = unwrap(raw)
        if res and isinstance(res, list):
             print(f"  ✅ list_documents success: Found {len(res)} users")
        elif res:
             print(f"  ⚠️ list_documents returned dict/other: {str(res)[:100]}")
    except Exception as e:
        print(f"  ❌ list_documents Failed: {e}")

    # 3.2 Get Doctype Info
    print(f"  🔹 Testing 'get_doctype_info'...")
    try:
        raw = registry.execute("get_doctype_info", {"doctype": "ToDo"})
        res = unwrap(raw)
        if res and isinstance(res, dict) and "fields" in res:
             print(f"  ✅ get_doctype_info success: Retrieved schema for ToDo")
    except Exception as e:
        print(f"  ❌ get_doctype_info Failed: {e}")

    # 3.3 Create & Delete Document
    print(f"  🔹 Testing CRUD on ToDo...")
    test_todo_id = None
    try:
        # Create
        raw = registry.execute("create_document", {
            "doctype": "ToDo",
            "data": {  # Fixed key from 'properties' to 'data'
                "description": "Phase 2 Test Item",
                "status": "Open"
            }
        })
        res = unwrap(raw)
        
        if res and isinstance(res, dict) and res.get("name"):
            test_todo_id = res.get("name")
            print(f"  ✅ create_document success: Created {test_todo_id}")
            
            # Delete
            del_raw = registry.execute("delete_document", {
                "doctype": "ToDo",
                "name": test_todo_id
            })
            del_res = unwrap(del_raw)
            if del_res:
                print(f"  ✅ delete_document success: {del_res}")
            
        else:
             print(f"  ❌ create_document failed: {raw}")
             
    except Exception as e:
        print(f"  ❌ CRUD Test Failed: {e}")
        # Cleanup
        if test_todo_id and frappe.db.exists("ToDo", test_todo_id):
            frappe.delete_doc("ToDo", test_todo_id)

    # 3.4 Navigate (Side effect check)
    print(f"  🔹 Testing 'navigate'...")
    try:
        raw = registry.execute("navigate", {"doctype": "Task", "view": "List"})
        res = unwrap(raw)
        if res and isinstance(res, dict) and res.get("action") == "navigate":
             print(f"  ✅ navigate success: Returns client action.")
    except Exception as e:
        print(f"  ❌ navigate Failed: {e}")
        
    # 4. Web Search (Via FrappeToolkit)
    print(f"\n[4] Testing Web Search (Connectivity via Toolkit):")
    try:
        toolkit = FrappeToolkit()
        print(f"  🔹 Attempting 'web_search' for 'Frappe Framework'...")
        # Direct call to Toolkit method (Agno style)
        res = toolkit.web_search("Frappe Framework latest version")
        
        if isinstance(res, str) and len(res) > 50:
             print(f"  ✅ web_search success: Retrieved results.")
        else:
             print(f"  ⚠️ web_search returned: {str(res)[:100]}")
    except Exception as e:
        print(f"  ❌ web_search Failed: {e}")

    print("\n✅ Phase 2 Testing Complete.")
