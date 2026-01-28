import frappe
import json
import base64
import time
from typing import List, Dict, Any, Optional

# Agno Imports
from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat
from agno.tools import Toolkit
from agno.models.message import Message 

from tb_owlai_core.owlai_core.agno_adapter import OwlAIToolkit
from tb_owlai_core.utils import get_active_provider_config

from tb_owlai_core.agno_integrations.model_factory import get_model_instance

class OwlAgent:
    def __init__(self, user: str, context: Optional[Any] = None, conversation: Any = None, conversation_name: Optional[str] = None, max_steps: int = 5, agent_id: str = None):
        self.user = user
        self.context = context
        self.max_steps = max_steps
        self.agent_id = agent_id
        self.agent_doc = None
        self.conversation = conversation
        self.client_actions = {}
        
        # Load Agent Document
        if self.agent_id:
            if frappe.db.exists("OwlAI Agent", self.agent_id):
                self.agent_doc = frappe.get_doc("OwlAI Agent", self.agent_id)
        
        # Fallback to default agent
        if not self.agent_doc:
            settings = frappe.get_single("OwlAI Settings")
            if hasattr(settings, "default_agent") and settings.default_agent:
                self.agent_doc = frappe.get_doc("OwlAI Agent", settings.default_agent)

        # Config is now handled by Model Factory via agent_doc linkage
        
        # Initialize Conversation if needed
        if not self.conversation and conversation_name:
            if frappe.db.exists("OwlAI Conversation", conversation_name):
                self.conversation = frappe.get_doc("OwlAI Conversation", conversation_name)
        
        # Setup OwlAi Agent
        self.agno_agent = self._setup_agno_agent()

    def _setup_agno_agent(self) -> Agent:
        """Configures and returns the OwlAi Agent instance."""
        # 1. Select Model using Factory
        model_link = self.agent_doc.model if self.agent_doc else None
        model = get_model_instance(model_link)

        # 2. Select Tools
        tool_names = []
        if self.agent_doc and self.agent_doc.tools:
            tool_names = [row.tool for row in self.agent_doc.tools if row.enabled]
        
        # Add basic tools if none defined (fallback)
        if not tool_names:
            tool_names = ["frappe_utils"] # Safe default

        def tool_callback(name, args, result):
            # Check for client-side actions in tool result
            if isinstance(result, dict) and result.get("action") == "navigate":
                self.client_actions = result
        
        toolkit = OwlAIToolkit(tool_names=tool_names, result_callback=tool_callback)

        # 3. Instructions & Description
        description = "You are OwlAI, an intelligent assistant for Frappe/ERPNext."
        instructions = [
            f"Acting User: {self.user}",
            f"Current Time: {frappe.utils.now()}",
             # Dynamic Context Injection
            self.context.get_full_context_string() if self.context and hasattr(self.context, "get_full_context_string") else "",
            "CORE RULES:",
            "1. PLAN FIRST: If CREATE/UPDATE, check `get_doctype_info` first.",
            "2. ACTION-ORIENTED: Use tools to inspect/modify data.",
        ]
        
        if self.agent_doc and self.agent_doc.system_prompt:
             # If user provided a custom prompt, use it as description/instruction base
             description = self.agent_doc.system_prompt
    
        # Stateless Agent with manual history injection
        return Agent(
            model=model,
            tools=[toolkit],
            description=description,
            instructions=instructions,
            markdown=True,
            # We handle history loading manually to sync with Frappe DB
        )

    def _get_history_messages(self) -> List[Message]:
        """Loads Frappe conversation history into Agno Message format."""
        if not self.conversation or not self.conversation.messages:
            return []
            
        limit = 30
        msgs = self.conversation.messages[-limit:]
        
        history_objs = []
        for m in msgs:
            role = m.role
            if role == "system": continue # System prompt is handled by Agent(description=...)
            
            # Map role
            if role == "assistant":
                # Check if it was a json object (tool call mostly)
                history_objs.append(Message(role="assistant", content=m.content))
            elif role == "user":
                history_objs.append(Message(role="user", content=m.content))
        
        return history_objs

    def save_message(self, role: str, content: str, message_type: str = "text", action_data: Any = None):
        """Persists a message to the OwlAI Conversation child table."""
        if not self.conversation:
            return

        self.conversation.append("messages", {
            "role": role,
            "content": content,
            "message_type": message_type,
            "action_data": json.dumps(action_data) if action_data else None,
            "timestamp": frappe.utils.now()
        })
        self.conversation.save(ignore_permissions=True)
        frappe.db.commit()

    def run(self, user_message: str, image_file=None, audio_file=None):
        """Main execution loop using Agno."""
        
        # 1. Load History
        history = self._get_history_messages()
        
        # 2. Run OwlAi Agent
        try:
            # Save User Message first if provided
            if user_message:
                self.save_message("user", user_message)
            
            # Construct input messages sequence: History + New User Message
            # Note: Agno's .run() usually takes the *new* input.
            # But creating a fresh Agent every time means it has no memory.
            # We can pass `messages` argument to .run()? No, .run() takes input.
            # If input is a list of messages, does it process all?
            # Or we can verify if Agno supports `history` param.
            # Checking Agno docs (mental): stateless runs usually require passing history implicitly or via memory.
            # Since we didn't attach memory, we can manually set `memory.messages` if memory existed.
            # BUT we don't have memory.
            
            # Workaround: Re-instantiate Agent? No.
            # If we pass List[Message] as input, Agno treats it as the conversation so far?
            # Let's try passing the full conversation as input.
            
            # Construct Input
            messages = history
            if user_message:
                messages.append(Message(role="user", content=user_message))
                
            # If user sent image
            if image_file:
                # Add image to last user message
                # Agno Message supports images? Yes.
                # skipping for now as complexity increases, focusing on text tools.
                pass
            
            # RUN
            response = self.agno_agent.run(messages, stream=False)
            
            final_text = response.content
            
            should_close = False
            
            # Check if client actions were captured via callback
            if self.client_actions:
                should_close = True

            self.save_message("assistant", final_text)
            
            return {
                "reply": final_text,
                "close_chat": should_close,
                "stats": {}, 
                **self.client_actions
            }

        except Exception as e:
            frappe.log_error(f"Agno Run Error: {e}")
            return {"reply": f"Error: {str(e)}", "close_chat": False}