
from typing import Optional, List, Dict, Any, Union, Tuple
from agno.db.base import BaseDb, SessionType
from agno.session.agent import AgentSession
from agno.session import Session
import frappe
import json

class FrappeStorage(BaseDb):
    """
    Storage backend for Agno Agents using Frappe's OwlAI Conversation DocType.
    """
    def __init__(self):
        super().__init__()

    def table_exists(self, table_name: str) -> bool:
        return True # We use DocTypes

    def get_latest_schema_version(self, table_name: str):
        return "1.0.0"

    def upsert_schema_version(self, table_name: str, version: str):
        pass

    # --- Sessions ---
    # --- Sessions ---
    def delete_session(self, session_id: str) -> bool:
        if frappe.db.exists("OwlAI Conversation", {"session_id": session_id}):
            name = frappe.db.get_value("OwlAI Conversation", {"session_id": session_id}, "name")
            frappe.delete_doc("OwlAI Conversation", name, ignore_permissions=True)
            return True
        return False

    def delete_sessions(self, session_ids: List[str]) -> None:
        for sid in session_ids:
            self.delete_session(sid)

    def get_session(
        self,
        session_id: str,
        session_type: SessionType = None, 
        user_id: Optional[str] = None,
        deserialize: Optional[bool] = True,
    ) -> Optional[Union[AgentSession, Dict[str, Any]]]:
        if not frappe.db.exists("OwlAI Conversation", {"session_id": session_id}):
            return None
            
        name = frappe.db.get_value("OwlAI Conversation", {"session_id": session_id}, "name")
        doc = frappe.get_doc("OwlAI Conversation", name)
        
        # 1. Try to load exact Agno blob if available
        if hasattr(doc, "agno_session_data") and doc.agno_session_data:
             try:
                 data = json.loads(doc.agno_session_data)
                 if deserialize:
                     # AgentSession is a dataclass in this version
                     try:
                        return AgentSession.from_dict(data)
                     except:
                        # Fallback if from_dict missing, try constructor
                        return AgentSession(**data)
                 return data
             except:
                 pass
        
        # 2. Fallback: Reconstruct from messages table
        # We need to import RunOutput to construct it properly
        from agno.run.agent import RunOutput
        from agno.models.message import Message

        messages = []
        for m in doc.messages:
             messages.append(Message(
                 role=m.role,
                 content=m.content
             ))
        
        # Create a single run encapsulating history
        initial_run = RunOutput(
            run_id="legacy_history",
            messages=messages,
            metrics={"input_tokens": 0} # Dummy metrics
        )

        session = AgentSession(
            session_id=session_id,
            agent_id="owlai_agent",
            user_id=doc.owner,
            runs=[initial_run],
            session_data={}
        )
        
        if deserialize:
            return session
        return session.to_dict() if hasattr(session, "to_dict") else vars(session)

    def get_sessions(self, *args, **kwargs):
        return []

    def rename_session(self, session_id: str, session_type: SessionType, session_name: str, deserialize: bool = True):
        return None

    def upsert_session(
        self, session: AgentSession, deserialize: Optional[bool] = True
    ) -> Optional[Union[AgentSession, Dict[str, Any]]]:
        
        conversation_id = session.session_id
        if not conversation_id: return None
        
        doc = None
        if not frappe.db.exists("OwlAI Conversation", {"session_id": conversation_id}):
            doc = frappe.new_doc("OwlAI Conversation")
            doc.session_id = conversation_id
            doc.title = f"Chat {conversation_id}"
        else:
            name = frappe.db.get_value("OwlAI Conversation", {"session_id": conversation_id}, "name")
            doc = frappe.get_doc("OwlAI Conversation", name)
            
        # 1. Update Messages Table (Readable in Desk)
        all_messages = []
        if session.runs:
            for run in session.runs:
                if run.messages:
                    all_messages.extend(run.messages)
        
        doc.messages = []
        for msg in all_messages:
             content = ""
             if isinstance(msg.content, str):
                 content = msg.content
             
             # Handle Tool Calls (Native)
             action_data = None
             if hasattr(msg, "tool_calls") and msg.tool_calls:
                 # agno ToolCall object needs serialization
                 try:
                     action_data = [t.to_dict() if hasattr(t, "to_dict") else t for t in msg.tool_calls]
                     # Flatten if single action for easier frontend handling (optional, but keep list for standard)
                     # The frontend likely expects a single object for "navigate" based on user screenshot implying "action_data" is a JSON object.
                     # Let's keep it as list of tool calls or specific format if we know it.
                     # However, older logic in router.py suggests action_data is a JSON string of a dict. 
                     # Let's serialize the list.
                     action_data = json.dumps(action_data)
                 except: pass

             # FALLBACK: Check if content IS a JSON tool call (Model chatting the JSON)
             if not action_data and content and content.strip().startswith("{") and "name" in content and "parameters" in content:
                 try:
                     possible_json = json.loads(content)
                     # Check if it looks like a tool call
                     if "name" in possible_json and "parameters" in possible_json:
                         # It matches the schema we saw in screenshot
                         # We treat this as the action_data
                         action_data = json.dumps([possible_json]) # Wrap in list to be consistent with tool_calls? 
                         # Or just the object? 
                         # router.py get_conversation_messages does json.loads(m.action_data)
                         # If we accept a list, frontend must handle list.
                         # If we accept dict, frontend handles dict.
                         # The screenshot showed {"name": "navigate"...} which is a single object.
                         # Let's save it as the object (or list of objects).
                         # Standard OpenAI tool_calls is a list.
                         # Let's assume we standardise on List of Actions. 
                         # But wait, FrappeToolkit.navigate returns a dict? 
                         # Let's stick to the extracted JSON object.
                         action_data = json.dumps(possible_json)
                 except: 
                     pass

             doc.append("messages", {
                 "role": msg.role,
                 "content": content[:100000], # truncate safely
                 "action_data": action_data
             })
             
        # 2. Update Raw Session Data (Persistence)
        try:
            # Use to_dict() if available (likely dataclass wizard or similar)
            if hasattr(session, "to_dict"):
                session_dict = session.to_dict()
                doc.agno_session_data = json.dumps(session_dict)
            else:
                 # Fallback to vars or manual construction
                 # Note: vars() might not include nested objects serialization
                 import dataclasses
                 if dataclasses.is_dataclass(session):
                     session_dict = dataclasses.asdict(session)
                     doc.agno_session_data = json.dumps(session_dict, default=str)
                 else:
                     doc.agno_session_data = json.dumps(session.__dict__, default=str)
        except Exception as e:
            print(f"Serialization Warning: {e}")
            doc.agno_session_data = "{}"
        doc.session_id = conversation_id # Ensure set
        
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return session

    def upsert_sessions(self, sessions, deserialize=True, preserve_updated_at=False):
        return []

    # --- Stubs for other abstract methods ---
    def clear_memories(self): pass
    def delete_user_memory(self, memory_id, user_id=None): pass
    def delete_user_memories(self, memory_ids, user_id=None): pass
    def get_all_memory_topics(self, user_id=None): return []
    def get_user_memory(self, memory_id, deserialize=True, user_id=None): return None
    def get_user_memories(self, *args, **kwargs): return []
    def get_user_memory_stats(self, *args, **kwargs): return [], 0
    def upsert_user_memory(self, memory, deserialize=True): return None
    def upsert_memories(self, memories, deserialize=True, preserve_updated_at=False): return []
    
    def get_metrics(self, *args, **kwargs): return [], 0
    def calculate_metrics(self): return None
    
    def delete_knowledge_content(self, id): pass
    def get_knowledge_content(self, id): return None
    def get_knowledge_contents(self, *args, **kwargs): return [], 0
    def upsert_knowledge_content(self, knowledge_row): return None
    
    def create_eval_run(self, eval_run): return None
    def delete_eval_runs(self, eval_run_ids): pass
    def get_eval_run(self, eval_run_id, deserialize=True): return None
    def get_eval_runs(self, *args, **kwargs): return []
    def rename_eval_run(self, eval_run_id, name, deserialize=True): return None
    
    def upsert_trace(self, trace): pass
    def get_trace(self, *args, **kwargs): return None
    def get_traces(self, *args, **kwargs): return [], 0
    def get_trace_stats(self, *args, **kwargs): return [], 0
    
    def create_span(self, span): pass
    def create_spans(self, spans): pass
    def get_span(self, span_id): return None
    def get_spans(self, *args, **kwargs): return []
    
    def clear_cultural_knowledge(self): pass
    def delete_cultural_knowledge(self, id): pass
    def get_cultural_knowledge(self, id): return None
    def get_all_cultural_knowledge(self, *args, **kwargs): return None
    def upsert_cultural_knowledge(self, cultural_knowledge): return None
    
    def get_learning(self, *args, **kwargs): return None
    def upsert_learning(self, *args, **kwargs): pass
    def delete_learning(self, id): return False
    def get_learnings(self, *args, **kwargs): return []

