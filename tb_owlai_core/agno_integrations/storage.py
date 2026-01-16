
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
        # logic: only use it if it seems valid (has runs or runs is not empty)
        use_blob = False
        if hasattr(doc, "agno_session_data") and doc.agno_session_data:
             try:
                 data = json.loads(doc.agno_session_data)
                 # Check if this data actually contains history
                 if data and isinstance(data, dict):
                     # If it has runs and they are not empty, OR if we trust it's a valid empty session (less likely if we have messages)
                     # Better heuristic: If doc.messages has rows but data["runs"] is empty, IGNORE blob.
                     
                     runs = data.get("runs", [])
                     has_runs = len(runs) > 0
                     has_messages = len(doc.messages) > 0
                     
                     if has_runs:
                         use_blob = True
                     elif not has_messages:
                         # accurate representation of empty state
                         use_blob = True
                     else:
                         # Messages exist but blob has no runs -> Blob is stale/corrupt. Fallback.
                         use_blob = False
                 
                 if use_blob:
                     if deserialize:
                         try:
                            # Try standard deserialization
                            return AgentSession.from_dict(data)
                         except:
                            # Fallback if from_dict missing or error
                            return AgentSession(**data)
                     return data
             except Exception as e:
                 # print(f"Blob load error: {e}")
                 pass
        
        # 2. Fallback: Reconstruct from messages table
        try:
            from agno.run.agent import RunOutput
            from agno.models.message import Message
    
            messages = []
            for m in doc.messages:
                 try:
                     # Parse action_data if exists to reconstruct tool calls properly?
                     # For now, content/role is most important for context.
                     tool_calls = None
                     # If we saved action_data, we might want to restore it?
                     # Agno message has 'tool_calls' field.
                     
                     messages.append(Message(
                         role=m.role,
                         content=m.content
                     ))
                 except: pass
            
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
        except Exception as e:
            frappe.log_error(f"Error reconstructing session: {e}")
            return None

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
                 try:
                     action_data = [t.to_dict() if hasattr(t, "to_dict") else t for t in msg.tool_calls]
                     action_data = json.dumps(action_data, default=str)
                 except: pass

             # FALLBACK: Check if content IS a JSON tool call
             if not action_data and content and content.strip().startswith("{") and "name" in content and "parameters" in content:
                 try:
                     possible_json = json.loads(content)
                     if "name" in possible_json and "parameters" in possible_json:
                         action_data = json.dumps(possible_json, default=str)
                 except: pass

             doc.append("messages", {
                 "role": msg.role,
                 "content": content[:100000], 
                 "action_data": action_data
             })
             
        # 2. Update Raw Session Data (Persistence)
        try:
            def safe_serialize(obj):
                if hasattr(obj, "to_dict"): return obj.to_dict()
                if hasattr(obj, "__dict__"): return obj.__dict__
                return str(obj)

            if hasattr(session, "to_dict"):
                session_dict = session.to_dict()
                doc.agno_session_data = json.dumps(session_dict, default=safe_serialize)
            else:
                 import dataclasses
                 if dataclasses.is_dataclass(session):
                     session_dict = dataclasses.asdict(session)
                     doc.agno_session_data = json.dumps(session_dict, default=safe_serialize)
                 else:
                     doc.agno_session_data = json.dumps(session.__dict__, default=safe_serialize)
        except Exception as e:
            # print(f"Serialization Warning: {e}")
            # Do NOT overwrite with "{}" if we have messages. 
            # Leave existing blob if serialization fails? Or write what we can?
            # Writing "{}" is dangerous as it triggers the empty load bug.
            pass
            
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

