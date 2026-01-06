import frappe
import json
import base64
import re
from typing import List, Dict, Any, Optional
from litellm import completion
import time
from tb_owlai_core.tool_registry import ToolRegistry
from tb_owlai_core.utils import get_active_provider_config


class OwlAgent:
    def __init__(self, user: str, context: Dict[str, Any], conversation: Any = None, conversation_name: Optional[str] = None, max_steps: int = 5):
        self.user = user
        self.context = context or {}
        self.max_steps = max_steps
        self.registry = ToolRegistry()
        self.config = get_active_provider_config()
        self.history = []
        self.conversation = conversation
        self.stats = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "tool_calls": []
        }
        
        if not self.conversation and conversation_name:
            if frappe.db.exists("OwlAI Conversation", conversation_name):
                self.conversation = frappe.get_doc("OwlAI Conversation", conversation_name)
        
        if self.conversation:
            self._load_history()

    def _load_history(self):
        """Loads conversation history into LLM format."""
        if not self.conversation or not self.conversation.messages:
            return
            
        # Limit to last 10 messages to keep context window clean but provide sufficient history
        msgs = self.conversation.messages[-10:]
        for m in msgs:
            # Map 'system' role from DB (observations) to 'user' for LLM context, 
            # or keep valid roles.
            role = m.role
            if role == "system":
                 # Observations are saved as 'system' but fed as 'user' in the loop
                role = "user" 
            
            if role in ["user", "assistant", "system"]:
                self.history.append({
                    "role": role,
                    "content": m.content
                })

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

    def get_system_prompt(self) -> str:
        """Constructs the optimized system prompt with Action-First directives."""
        tools = self.registry.get_tools_schema()
        
        prompt = [
            "You are OwlAI, the Native Intelligence Layer for Frappe/ERPNext.",
            f"Acting User: {self.user}",
            f"Current Time: {frappe.utils.now()}",
            f"Current Route: {json.dumps(self.context.get('route'))}",
            "\nCORE RULES:",
            "1. ACTION: If a user request implies a system action (viewing, creating, searching), use a tool immediately.",
            "2. SMART NAVIGATION: Use the 'Maps' tool for requests like 'Go to Sales Orders' or 'Show me my tasks'.",
            "3. NO HALLUCINATION: If a tool returns a 'LinkValidationError' (record not found), ask the user if they want to create it.",
            "4. RESPONSE FORMAT: If calling a tool, output ONLY valid JSON in this format: { \"action\": \"ToolName\", \"args\": { <arguments> } }.",
            "5. NO INNER MONOLOGUE: Do not output thoughts. If you need to use a tool, output ONLY the JSON object. If the task is complete, Close the conversation and Navigate to that route. Unless explicitly other instrcutions given by user.",
            "6. SCHEMA VALIDATION: Before creating a new document, if the field names are not explicitly known from context, use 'get_doctype_info' to fetch the schema. Do not guess field names (e.g., use 'first_name' instead of 'name').",
            "\nAVAILABLE TOOLS:",
            json.dumps(tools, indent=2)
        ]
        
        # Inject Custom System Prompt Additions from Settings
        settings = frappe.get_single("OwlAI Settings")
        if settings.system_prompt_additions:
            prompt.append("\nADDITIONAL INSTRUCTIONS:")
            prompt.append(settings.system_prompt_additions)

        return "\n".join(prompt)

    def _parse_llm_response(self, text: str) -> Dict[str, Any]:
        """Robustly extracts JSON tool calls from LLM text, handling markdown blocks."""
        if not text: return {"type": "text", "content": ""}
        
        # 1. Try extracting from code blocks first
        if "```json" in text:
            try:
                block = text.split("```json")[1].split("```")[0].strip()
                data = json.loads(block)
                if "action" in data:
                    return {"type": "tool_call", "tool": data["action"], "args": data.get("args", {})}
            except (json.JSONDecodeError, IndexError):
                pass

        # 2. Try finding raw JSON object (brackets)
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = text[start:end+1]
                data = json.loads(json_str)
                if "action" in data:
                    return {"type": "tool_call", "tool": data["action"], "args": data.get("args", {})}
        except json.JSONDecodeError:
            pass
        
        return {"type": "text", "content": text}

    def run(self, user_message: str, image_file=None, audio_file=None):
        """Main execution loop (Agentic Loop)."""
        if not self.config:
            return {"message": "AI Provider not configured.", "close_chat": False}

        # 1. Prepare messages
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        messages.extend(self.history)

        # 2. Handle Multi-modal Input (Vision)
        user_content = []
        if user_message:
            user_content.append({"type": "text", "text": user_message})
        
        if image_file:
            # Note: Requires a vision-capable model in config
            image_b64 = base64.b64encode(image_file.read()).decode('utf-8')
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
            })
            self.save_message("user", user_message or "Analyze image", message_type="image")
        else:
            self.save_message("user", user_message)

        # If user_content has only text, simplify to string for broader compatibility
        final_user_content = user_content
        if len(user_content) == 1 and user_content[0]["type"] == "text":
            final_user_content = user_message
        
        messages.append({"role": "user", "content": final_user_content})

        client_action = {}
        current_step = 0
        final_text = None
        should_close = False

        while current_step < self.max_steps:
            current_step += 1
            
            try:
                settings = frappe.get_single("OwlAI Settings")
                temperature =  settings.response_temperature if settings.response_temperature is not None else 0.7

                response = completion(
                    model=self.config.get("model"),
                    messages=messages,
                    api_key=self.config.get("api_key"),
                    api_base=self.config.get("api_base"),
                    temperature=temperature,
                    stop=["\nObservation:", "Observation:", "User:", "Note:"]
                )
                
                # Track Token Usage
                if hasattr(response, 'usage'):
                    self.stats["prompt_tokens"] += response.usage.prompt_tokens
                    self.stats["completion_tokens"] += response.usage.completion_tokens
                    self.stats["total_tokens"] += response.usage.total_tokens

            except Exception as e:
                return {"reply": f"LLM Connection Error: {str(e)}", "close_chat": False}

            raw_content = response.choices[0].message.content or ""
            parsed = self._parse_llm_response(raw_content)

            if parsed["type"] == "tool_call":
                tool_name = parsed["tool"]
                tool_args = parsed["args"]
                self.stats["tool_calls"].append({"tool": tool_name, "args": tool_args})
                
                try:
                    self.save_message("assistant", f"Calling {tool_name}...", message_type="action", action_data=parsed)
                    
                    # Notify frontend via Realtime API for Toast
                    frappe.publish_realtime("msgprint", {
                        "message": f"OwlAI is executing {tool_name}...",
                        "alert": True,
                        "indicator": "blue"
                    }, user=self.user)

                    # Execute
                    tool_start = time.time()
                    result = self.registry.execute(tool_name, tool_args)
                    tool_duration = time.time() - tool_start
                    
                    # Update stats with duration
                    if self.stats["tool_calls"]:
                        self.stats["tool_calls"][-1]["duration"] = tool_duration

                    # Unwrap tool result if it's from BaseTool (wrapped in success/result/time)
                    tool_output = result.get("result") if isinstance(result, dict) and "result" in result else result

                    # Handle Client-Side Actions (e.g. Navigation from Maps tool)
                    if isinstance(tool_output, dict) and tool_output.get("action"):
                        client_action = tool_output
                        should_close = True
                        final_text = tool_output.get("message", "Processing action...")
                        # If the tool provides a message, let's show that.
                        break
                    
                    # Feed observation back
                    observation = f"Observation from {tool_name}: {json.dumps(result, default=str)}"
                    
                    # Sanitize assistant message in history to ensure clean JSON for future turns
                    clean_content = json.dumps({"action": tool_name, "args": tool_args})
                    messages.append({"role": "assistant", "content": clean_content})
                    
                    # Ensure observation is valid string
                    messages.append({"role": "user", "content": str(observation)})
                    self.save_message("system", observation)

                except Exception as e:
                    error_obs = f"System Error: {str(e)}"
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append({"role": "user", "content": error_obs})
                    self.save_message("system", error_obs)
            else:
                final_text = parsed["content"]
                self.save_message("assistant", final_text)
                break

        response_data = {
            "reply": final_text or "Task processed.",
            "close_chat": should_close,
            "stats": self.stats,
            "messages": messages
        }
        
        # Merge client actions (action, doctype, view, etc.)
        if client_action:
            response_data.update(client_action)
            
        return response_data