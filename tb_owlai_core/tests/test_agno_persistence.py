
import frappe
import json
from tb_owlai_core.agno_integrations.storage import FrappeStorage
from agno.session.agent import AgentSession
from agno.run.agent import RunOutput
from agno.models.message import Message

def test_persistence():
    try:
        storage = FrappeStorage()
        
        # 1. Create a dummy session with distinct data
        session_id = "TEST-SESSION-001"
        
        # Ensure it doesn't exist
        if frappe.db.exists("OwlAI Conversation", session_id):
            frappe.delete_doc("OwlAI Conversation", session_id, ignore_permissions=True)
        
        dummy_run = RunOutput(
            run_id="run_1",
            messages=[Message(role="user", content="Hello")],
            metrics={"input_tokens": 10},
        )
        
        session = AgentSession(
            session_id=session_id,
            agent_id="test_agent",
            runs=[dummy_run],
            session_data={"custom_variable": "should_be_saved"}
        )
        
        print(f"Saving Session {session_id} with custom_variable...")
        storage.upsert_session(session)
        frappe.db.commit() # Ensure commit
        
        # 2. Retrieve it
        print("Retrieving Session...")
        # Force fresh read from DB to avoid caching issues, though new storage instance helps
        storage2 = FrappeStorage()
        loaded_session = storage2.get_session(session_id, session_type=None)
        
        # 3. Validation
        if not loaded_session:
            print("FAIL: Session could not be loaded.")
            return

        print(f"Loaded Session Data: {loaded_session.session_data}")
        
        if loaded_session.session_data.get("custom_variable") == "should_be_saved":
            print("PASS: Session Data persisted.")
        else:
            print("FAIL: Session Data LOST! (Expected 'should_be_saved')")
            

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {e}")

