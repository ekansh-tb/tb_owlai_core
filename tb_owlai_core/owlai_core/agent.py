import frappe
import json
import time
import traceback
import base64
from frappe.utils import get_link_to_form
from litellm import completion
from tb_owlai_core.tool_registry import ToolRegistry
from tb_owlai_core.utils import get_active_provider_config
from tb_owlai_core.utils.context import OwlContext

class OwlAgent:
    def __init__(self, user, context, conversation=None, max_steps=5):
        self.user = user
        
        # Support both OwlContext object and raw dict
        if isinstance(context, dict):
             self.context = OwlContext(
                 route=context.get('route'),
                 form_data=context.get('form_data'),
                 selected_items=context.get('selected_items')
             )
        else:
             self.context = context

        self.conversation = conversation
        self.max_steps = max_steps
        self.registry = ToolRegistry()
        self.config = get_active_provider_config()
        self.history = []
        if self.conversation:
            self._load_history()

    def _load_history(self):
        """Loads conversation history into LLM format"""
        if not self.conversation or not self.conversation.messages:
            return
            
        # Get last 50 messages
        limit = 50
        msgs = self.conversation.messages[-limit:] if len(self.conversation.messages) > limit else self.conversation.messages
        
        for m in msgs:
            if m.role in ["user", "assistant"]:
                self.history.append({
                    "role": m.role,
                    "content": m.content
                })

    def save_message(self, role, content, message_type="text", action_data=None):
        """Save a message to the conversation doc"""
        if not self.conversation: return

        self.conversation.append("messages", {
            "role": role,
            "content": content[:100000] if content else "",
            "message_type": message_type,
            "action_data": json.dumps(action_data) if action_data else None
        })
        self.conversation.save(ignore_permissions=True)
        frappe.db.commit()

    def run(self, user_message, image_file=None, audio_file=None):
        """
        Main execution loop (The Agentic Loop).
        """
        if not self.config:
            return {"reply": "AI Provider not configured."}

        # 1. Prepare Initial Messages
        system_prompt = self.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add History
        messages.extend(self.history)

        # Add User Input
        user_content = []
        user_text_for_storage = user_message or ""
        
        if user_message:
             user_content.append({"type": "text", "text": user_message})
        
        if image_file:
             # Basic Image Handling
             image_bytes = image_file.read()
             image_b64 = base64.b64encode(image_bytes).decode('utf-8')
             user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
             })
             user_text_for_storage = f"[Image Attached] {user_message or 'Analyze this image'}"
             
        if audio_file:
             user_text_for_storage = f"[Audio Attached] {user_message or 'Voice command'}"

        if user_content:
            messages.append({"role": "user", "content": user_content})
            self.save_message("user", user_text_for_storage, 
                              message_type="image" if image_file else "text")
        else:
             if not audio_file:
                 return {"reply": "I didn't receive any input."}

        current_step = 0
        final_response = None
        client_actions = []
        
        while current_step < self.max_steps:
            current_step += 1
            
            # CALL LLM
            try:
                response = self._call_llm(messages)
            except Exception as e:
                return {"reply": f"Error interacting with AI: {str(e)}"}

            content = response.choices[0].message.content
            
            # Parse
            action_data = self._parse_json(content)
            
            # Save Assistant Message
            self.save_message("assistant", content, 
                              message_type="action" if action_data else "text",
                              action_data=action_data)
            
            messages.append({"role": "assistant", "content": content})
            
            # DECIDE: Action or Answer?
            if action_data and "action" in action_data:
                tool_name = action_data["action"]
                tool_args = action_data.get("args") or {}
                
                # Execute Tool
                try:
                    tool_result = self.registry.execute_tool(tool_name, tool_args)
                    
                    # Check for Client Side Action
                    if isinstance(tool_result, dict) and "action" in tool_result:
                        client_actions.append(tool_result)
                    
                    # Add Observation
                    observation = f"Tool '{tool_name}' Result: {json.dumps(tool_result, default=str)}"
                    messages.append({"role": "user", "content": f"Observation: {observation}"}) 
                    
                    # Persist observation for history
                    self.save_message("system", f"Observation: {observation}") 
                    
                except Exception as e:
                    messages.append({"role": "user", "content": f"System Error: Tool Execution Failed: {str(e)}"})
            else:
                # No action = Final Answer
                final_response = content
                break
                
        result = {"reply": final_response or "Task composed of multiple steps."}
        
        # Merge Client Actions (Take the last one for now)
        if client_actions:
            result.update(client_actions[-1])
            
        return result

    def get_system_prompt(self):
        tools = self.registry.get_available_tools()
        context_str = self.context.get_full_context_string() # Uses OwlContext for Scheme/Data
        
        prompt = [
            f"You are OwlAI, an intelligent ERP assistant integrated into Frappe Framework.",
            f"Current User: {self.user}",
            f"Current Time: {frappe.utils.now()}",
            f"\n{context_str}",  # Injected Visual Context from OwlContext
            f"\nAVAILABLE TOOLS:\n{json.dumps(tools, indent=2)}",
            "\nCAPABILITIES:",
            "1. You can access and manipulate data within this ERP system.",
            "2. You MUST use the provided tools to perform actions.",
            "3. You operate with the permissions of the current logged-in user.",
            "4. If a user asks to create a document, first check the Schema to know required fields.",
            "\nCRITICAL RULES:",
            "- ALWAYS try to use a tool if the user intent implies an action (searching, reading, creating).",
            "- Output valid JSON when calling tools.",
            "- Format: { \"action\": \"tool_name\", \"args\": { ... } }",
            "- If you lack information (e.g., missing mandatory field), ASK the user.",
             "2. RESPONSE FORMAT:",
            "   - If you need to perform an action, return a JSON object: { \"action\": \"tool_name\", \"args\": { ... } }",
            "   - If you want to answer the user, just write text.",
            "- Be concise and professional."
        ]
        
        return "\n".join(prompt)

    def _call_llm(self, messages):
        return completion(
            model=self.config.get("model"),
            messages=messages,
            api_key=self.config.get("api_key"),
            api_base=self.config.get("api_base")
        )

    def _parse_json(self, text):
        """Robust JSON extraction"""
        if not text: return None
        clean = text.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()
            
        try:
            if clean.startswith("{"):
                return json.loads(clean)
        except:
            pass
        return None
