
from typing import Optional, List, Dict, Any, Union, Tuple
from agno.db.base import BaseDb, SessionType
from agno.session import AgentSession
from agno.db.schemas.memory import UserMemory
from agno.db.schemas.knowledge import KnowledgeRow
import frappe
import json

class FrappeStorage(BaseDb):
    """
    Storage backend for OwlAi Agents using Frappe DocTypes:
    - OwlAI Conversation (Sessions)
    - OwlAI User Memory (Memories)
    - OwlAI Knowledge Item (Knowledge)
    """
    def __init__(self):
        super().__init__()

    def table_exists(self, table_name: str) -> bool:
        return True # Virtual check

    def get_latest_schema_version(self, table_name: str):
        return "1.0.0"

    def upsert_schema_version(self, table_name: str, version: str):
        pass

    # --- Sessions ---
    def delete_session(self, session_id: str) -> bool:
        name = None
        if frappe.db.exists("OwlAI Conversation", session_id):
            name = session_id
        elif frappe.db.exists("OwlAI Conversation", {"session_id": session_id}):
            name = frappe.db.get_value("OwlAI Conversation", {"session_id": session_id}, "name")
            
        if name:
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
        if frappe.db.exists("OwlAI Conversation", session_id):
            name = session_id
        elif frappe.db.exists("OwlAI Conversation", {"session_id": session_id}):
            name = frappe.db.get_value("OwlAI Conversation", {"session_id": session_id}, "name")
        else:
            return None
            
        doc = frappe.get_doc("OwlAI Conversation", name)
        
        # Prefer Blob
        if doc.agno_session_data:
            try:
                data = json.loads(doc.agno_session_data)
                # Validation: if blob is empty but messages exist, ignore blob
                if not data.get("runs") and doc.messages:
                    pass # Fallback to reconstruction
                else:
                    if deserialize:
                        return AgentSession.from_dict(data)
                    return data
            except: pass
        
        # Reconstruction Fallback (Legacy)
        return self._reconstruct_session_from_messages(doc, session_id, deserialize)

    def _reconstruct_session_from_messages(self, doc, session_id, deserialize):
        try:
            from agno.run.agent import RunOutput
            from agno.models.message import Message
            messages = []
            for m in doc.messages:
                messages.append(Message(role=m.role, content=m.content))
            
            initial_run = RunOutput(
                run_id="legacy_history",
                messages=messages,
                metrics={"input_tokens": 0}
            )
            session = AgentSession(
                session_id=session_id,
                agent_id="owlai_agent",
                user_id=doc.owner,
                runs=[initial_run],
                session_data={}
            )
            return session if deserialize else session.to_dict()
        except: return None

    def get_sessions(self, *args, **kwargs):
        # Implementation for listing sessions if needed
        return []

    def rename_session(self, session_id: str, session_type: SessionType, session_name: str, deserialize: bool = True):
        return None

    def upsert_session(
        self, session: AgentSession, deserialize: Optional[bool] = True
    ) -> Optional[Union[AgentSession, Dict[str, Any]]]:
        
        conversation_id = session.session_id
        if not conversation_id: return None
        
        doc = None
        if frappe.db.exists("OwlAI Conversation", conversation_id):
            doc = frappe.get_doc("OwlAI Conversation", conversation_id)
            if not doc.session_id:
                doc.session_id = conversation_id
        elif frappe.db.exists("OwlAI Conversation", {"session_id": conversation_id}):
            name = frappe.db.get_value("OwlAI Conversation", {"session_id": conversation_id}, "name")
            doc = frappe.get_doc("OwlAI Conversation", name)
        else:
            doc = frappe.new_doc("OwlAI Conversation")
            doc.session_id = conversation_id
            doc.title = f"Chat {conversation_id}"
            
        # Update Messages Table
        doc.messages = []
        all_messages = []
        if session.runs:
            for run in session.runs:
                if run.messages:
                    all_messages.extend(run.messages)
        
        for msg in all_messages:
            content = msg.content if isinstance(msg.content, str) else ""
            action_data = None
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                 try:
                     action_data = json.dumps([t.to_dict() for t in msg.tool_calls], default=str)
                 except: pass

            message_type = "text"
            if action_data and action_data != "[]":
                message_type = "action"
                # If content is empty (typical for tool call messages), use action_data as content
                # for backward compatibility and frontend rendering.
                if not content:
                    content = action_data

            doc.append("messages", {
                "role": msg.role,
                "content": content[:100000], 
                "action_data": action_data,
                "message_type": message_type
            })
            
        # Save Blob
        try:
            doc.agno_session_data = json.dumps(session.to_dict(), default=str)
        except: pass
        
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return session

    def upsert_sessions(self, sessions: List[AgentSession]) -> List[AgentSession]:
        for s in sessions:
            self.upsert_session(s)
        return sessions

    # --- Memories (OwlAI User Memory) ---
    def upsert_user_memory(self, memory: UserMemory, deserialize=True) -> Optional[UserMemory]:
        # UserMemory usually has: user_id, memory_id, memory (dict/text), ...
        user = memory.user_id or frappe.session.user
        content = memory.memory if isinstance(memory.memory, str) else json.dumps(memory.memory)
        # Check duplicate by content/topic? Agno usually manages memory_id if provided?
        # For now, simplistic insert.
        
        mem_doc = frappe.new_doc("OwlAI User Memory")
        mem_doc.user = user
        mem_doc.content = content
        mem_doc.memory_type = "Fact" # Default
        mem_doc.save(ignore_permissions=True)
        frappe.db.commit()
        return memory

    def upsert_memories(self, memories: List[UserMemory], deserialize=True, preserve_updated_at=False) -> List[UserMemory]:
        for m in memories:
            self.upsert_user_memory(m)
        return memories

    def get_user_memories(self, user_id: str, limit: int = 10, **kwargs) -> List[UserMemory]:
        filters = {"user": user_id}
        docs = frappe.get_all("OwlAI User Memory", filters=filters, fields=["name", "content", "creation"], limit=limit)
        
        memories = []
        for d in docs:
             memories.append(UserMemory(
                 memory=d.content,
                 user_id=user_id,
                 created_at=d.creation,
                 updated_at=d.creation
             ))
        return memories

    # --- Knowledge (OwlAI Knowledge Base) ---
    def upsert_knowledge_content(self, knowledge_row: Any) -> None:
         # knowledge_row usually has: content, meta_data, etc.
         # We map to OwlAI Knowledge Base
         
         content = getattr(knowledge_row, "content", "")
         name = getattr(knowledge_row, "name", "Untitled")
         
         doc = frappe.new_doc("OwlAI Knowledge Base")
         doc.title = name[:140]
         doc.content = content
         doc.save(ignore_permissions=True)
         frappe.db.commit()

    def get_knowledge_content(self, id: str):
        # Retrieve by name or ID
        pass
        
    def search_knowledge(self, query: str, limit: int = 5):
        # Naive keyword search for now
        # Ideally utilizes Vector Index if pgvector is setup
        docs = frappe.db.sql("""
            SELECT content FROM `tabOwlAI Knowledge Base`
            WHERE content LIKE %s LIMIT %s
        """, (f"%{query}%", limit), as_dict=True)
        
        return [d.content for d in docs]
    
    # --- Other stubs ---
    def clear_memories(self): pass
    def delete_user_memory(self, memory_id, user_id=None): pass
    def delete_user_memories(self, memory_ids, user_id=None): pass
    def get_all_memory_topics(self, user_id=None): return []
    def get_user_memory(self, memory_id, deserialize=True, user_id=None): return None
    def get_user_memory_stats(self, *args, **kwargs): return [], 0
    # def upsert_memories(self, memories, deserialize=True, preserve_updated_at=False): return []
    def get_metrics(self, *args, **kwargs): return [], 0
    def calculate_metrics(self): return None
    def delete_knowledge_content(self, id): pass
    def get_knowledge_contents(self, *args, **kwargs): return [], 0
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

    # --- Async Stubs (to satisfy Agno abstract methods) ---
    async def table_exists_async(self, table_name: str) -> bool: return True
    async def get_latest_schema_version_async(self, table_name: str): return "1.0.0"
    async def upsert_schema_version_async(self, table_name: str, version: str): pass
    async def delete_session_async(self, session_id: str): return False
    async def delete_sessions_async(self, session_ids: List[str]): pass
    async def get_session_async(self, *args, **kwargs): return None
    async def get_sessions_async(self, *args, **kwargs): return []
    async def rename_session_async(self, *args, **kwargs): return None
    async def upsert_session_async(self, *args, **kwargs): return None
    async def clear_memories_async(self): pass
    async def delete_user_memory_async(self, *args, **kwargs): pass
    async def delete_user_memories_async(self, *args, **kwargs): pass
    async def get_all_memory_topics_async(self, *args, **kwargs): return []
    async def get_user_memory_async(self, *args, **kwargs): return None
    async def get_user_memories_async(self, *args, **kwargs): return []
    async def get_user_memory_stats_async(self, *args, **kwargs): return [], 0
    async def upsert_user_memory_async(self, *args, **kwargs): return None
    async def get_metrics_async(self, *args, **kwargs): return [], 0
    async def calculate_metrics_async(self): return None
    async def delete_knowledge_content_async(self, id: str): pass
    async def get_knowledge_content_async(self, id: str): return None
    async def get_knowledge_contents_async(self, *args, **kwargs): return [], 0
    async def upsert_knowledge_content_async(self, knowledge_row: KnowledgeRow): pass
    async def create_eval_run_async(self, eval_run): return None
    async def delete_eval_runs_async(self, eval_run_ids): pass
    async def get_eval_run_async(self, eval_run_id): return None
    async def get_eval_runs_async(self, *args, **kwargs): return []
    async def rename_eval_run_async(self, *args, **kwargs): return None
    async def upsert_trace_async(self, trace): pass
    async def get_trace_async(self, *args, **kwargs): return None
    async def get_traces_async(self, *args, **kwargs): return [], 0
    async def get_trace_stats_async(self, *args, **kwargs): return [], 0
    async def create_span_async(self, span): pass
    async def create_spans_async(self, spans): pass
    async def get_span_async(self, span_id): return None
    async def get_spans_async(self, *args, **kwargs): return []
    async def clear_cultural_knowledge_async(self): pass
    async def delete_cultural_knowledge_async(self, id): pass
    async def get_cultural_knowledge_async(self, id): return None
    async def get_all_cultural_knowledge_async(self, *args, **kwargs): return None
    async def upsert_cultural_knowledge_async(self, cultural_knowledge): return None
    async def get_learning_async(self, *args, **kwargs): return None
    async def upsert_learning_async(self, *args, **kwargs): pass
    async def delete_learning_async(self, id): return False
    async def get_learnings_async(self, *args, **kwargs): return []
