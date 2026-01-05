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
            self.conversation = frappe.get_doc("OwlAI Conversation", conversation_name)
        
        if self.conversation:
            self._load_history()

    def _load_history(self):
        """Loads conversation history into LLM format, skipping system/tool logs for the prompt."""
        if not self.conversation or not self.conversation.messages:
            return
            
        # Limit to last 20 messages to keep context window clean
        msgs = self.conversation.messages[-5:]
        for m in msgs:
            if m.role in ["user", "assistant"]:
                self.history.append({
                    "role": m.role,
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
            "1. ACTION-FIRST: If a user request implies a system action (viewing, creating, searching), use a tool immediately.",
            "2. SMART NAVIGATION: Use the 'Maps' tool for requests like 'Go to Sales Orders' or 'Show me my tasks'.",
            "3. NO HALLUCINATION: If a tool returns a 'LinkValidationError' (record not found), ask the user if they want to create it.",
            "4. RESPONSE FORMAT: If calling a tool, output ONLY valid JSON. If answering a question, use clear text.",
            "\nAVAILABLE TOOLS:",
            json.dumps(tools, indent=2)
        ]
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
            except json.JSONDecodeError:
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

        messages.append({"role": "user", "content": user_content if image_file else user_message})

        current_step = 0
        final_text = ""
        should_close = False

        while current_step < self.max_steps:
            current_step += 1
            
            try:
                response = completion(
                    model=self.config.get("model"),
                    messages=messages,
                    api_key=self.config.get("api_key"),
                    api_base=self.config.get("api_base")
                )
                
                # Track Token Usage
                if hasattr(response, 'usage'):
                    self.stats["prompt_tokens"] += response.usage.prompt_tokens
                    self.stats["completion_tokens"] += response.usage.completion_tokens
                    self.stats["total_tokens"] += response.usage.total_tokens

            except Exception as e:
                return {"message": f"LLM Connection Error: {str(e)}", "close_chat": False}

            raw_content = response.choices[0].message.content
            parsed = self._parse_llm_response(raw_content)

            if parsed["type"] == "tool_call":
                tool_name = parsed["tool"]
                tool_args = parsed["args"]
                self.stats["tool_calls"].append({"tool": tool_name, "args": tool_args})
                
                try:
                    self.save_message("assistant", f"Calling {tool_name}...", message_type="action", action_data=parsed)
                    
                    # Execute
                    tool_start = time.time()
                    result = self.registry.execute(tool_name, tool_args)
                    tool_duration = time.time() - tool_start
                    
                    # Update stats with duration
                    # Find the last tool call we just added (or modify how we add it)
                    if self.stats["tool_calls"]:
                        self.stats["tool_calls"][-1]["duration"] = tool_duration

                    # Handle Auto-Close for Navigation
                    if tool_name in ["navigate", "Maps"]:
                        should_close = True
                        final_text = "I've navigated you to the requested page."
                        break
                    
                    # Feed observation back
                    observation = f"Observation from {tool_name}: {json.dumps(result, default=str)}"
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append({"role": "user", "content": observation})
                    self.save_message("system", observation)

                except Exception as e:
                    error_obs = f"System Error: {str(e)}"
                    messages.append({"role": "user", "content": error_obs})
            else:
                final_text = parsed["content"]
                self.save_message("assistant", final_text)
                break

        return {
            "message": final_text or "Task processed.",
            "close_chat": should_close,
            "stats": self.stats,
            "messages": messages
        }

# import frappe
# import json
# import base64
# from typing import List, Dict, Any
# from litellm import completion
# from tb_owlai_core.tool_registry import ToolRegistry
# from tb_owlai_core.utils import get_active_provider_config
# from tb_owlai_core.utils.context import OwlContext

# class OwlAgent:
#     def __init__(self, user, context, conversation=None, max_steps=5):
#         self.user = user
#         if isinstance(context, dict):
#              self.context = OwlContext(
#                  route=context.get('route'),
#                  form_data=context.get('form_data'),
#                  selected_items=context.get('selected_items')
#              )
#         else:
#              self.context = context

#         self.conversation = conversation
#         self.max_steps = max_steps
#         self.registry = ToolRegistry()
#         self.config = get_active_provider_config()
#         self.history = []
#         if self.conversation:
#             self._load_history()

#     def _load_history(self):
#         """Loads conversation history into LLM format"""
#         if not self.conversation or not self.conversation.messages:
#             return
            
#         limit = 50
#         msgs = self.conversation.messages[-limit:] if len(self.conversation.messages) > limit else self.conversation.messages
        
#         for m in msgs:
#             if m.role in ["user", "assistant"]:
#                 self.history.append({
#                     "role": m.role,
#                     "content": m.content
#                 })

#     def save_message(self, role, content, message_type="text", action_data=None):
#         """Save a message to the conversation doc"""
#         if not self.conversation: return

#         self.conversation.append("messages", {
#             "role": role,
#             "content": content[:100000] if content else "",
#             "message_type": message_type,
#             "action_data": json.dumps(action_data) if action_data else None
#         })
#         self.conversation.save(ignore_permissions=True)
#         frappe.db.commit()

#     def run(self, user_message, image_file=None, audio_file=None):
#         """
#         Main execution loop (The Agentic Loop).
#         """
#         if not self.config:
#             return {"reply": "AI Provider not configured."}

#         # 1. Prepare Initial Messages
#         system_prompt = self.get_system_prompt()
#         messages = [{"role": "system", "content": system_prompt}]
        
#         # Add History
#         messages.extend(self.history)

#         # Add User Input
#         user_content = []
#         user_text_for_storage = user_message or ""
        
#         if user_message:
#              user_content.append({"type": "text", "text": user_message})
        
#         if image_file:
#              # Basic Image Handling
#              image_bytes = image_file.read()
#              image_b64 = base64.b64encode(image_bytes).decode('utf-8')
#              user_content.append({
#                 "type": "image_url",
#                 "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
#              })
#              user_text_for_storage = f"[Image Attached] {user_message or 'Analyze this image'}"
             
#         if audio_file:
#              user_text_for_storage = f"[Audio Attached] {user_message or 'Voice command'}"

#         if user_content:
#             messages.append({"role": "user", "content": user_content})
#             self.save_message("user", user_text_for_storage, 
#                               message_type="image" if image_file else "text")
#         else:
#              if not audio_file:
#                  return {"reply": "I didn't receive any input."}

#         current_step = 0
#         final_response = None
#         client_actions = []
        
#         while current_step < self.max_steps:
#             current_step += 1
            
#             # CALL LLM
#             try:
#                 response = self._call_llm(messages)
#             except Exception as e:
#                 return {"reply": f"Error interacting with AI: {str(e)}"}

#             content = response.choices[0].message.content
            
#             # Parse
#             action_data = self._parse_json(content)
            
#             # Save Assistant Message
#             self.save_message("assistant", content, 
#                               message_type="action" if action_data else "text",
#                               action_data=action_data)
            
#             messages.append({"role": "assistant", "content": content})
            
#             # DECIDE: Action or Answer?
#             if action_data and "action" in action_data:
#                 tool_name = action_data["action"]
#                 tool_args = action_data.get("args") or {}
                
#                 # Execute Tool
#                 try:
#                     tool_result = self.registry.execute_tool(tool_name, tool_args)
                    
#                     # Check for Client Side Action
#                     if isinstance(tool_result, dict) and "action" in tool_result:
#                         client_actions.append(tool_result)
                    
#                     # Add Observation
#                     observation = f"Tool '{tool_name}' Result: {json.dumps(tool_result, default=str)}"
#                     messages.append({"role": "user", "content": f"Observation: {observation}"}) 
                    
#                     # Persist observation for history
#                     self.save_message("system", f"Observation: {observation}") 
                    
#                 except Exception as e:
#                     messages.append({"role": "user", "content": f"System Error: Tool Execution Failed: {str(e)}"})
#             else:
#                 # No action = Final Answer
#                 final_response = content
#                 break
                
#         result = {"reply": final_response or "Task composed of multiple steps."}
        
#         # Merge Client Actions (Take the last one for now)
#         if client_actions:
#             result.update(client_actions[-1])
            
#         return result

#     def get_system_prompt(self):
#         tools = self.registry.get_available_tools()
#         context_str = self.context.get_full_context_string() 
        
#         prompt = [
#             f"You are OwlAI, an intelligent ERP assistant integrated into Frappe Framework.",
#             f"You are acting as user: {self.user}",
#             f"Current Time: {frappe.utils.now()}",
#             f"\n{context_str}", 
#             f"\nAVAILABLE TOOLS SCHEMA:\n{json.dumps(tools, indent=2)}",
#             "1. ACTION-FIRST: If a user asks something that requires data or navigation, USE A TOOL immediately.",
#             "2. NAVIGATION: For 'Go to [DocType]' or 'Show me...', use the 'Maps' tool. Prioritize 'Maps' over text.",
#             "3. FILTERED VIEWS: For 'Pending Sales Orders', use 'Maps' with 'filters' argument (e.g. {'status': 'Pending'}).",
#             "4. METRICS + ACTION: If user asks 'Sales Amount', calculate it (or use Sandbox/Report), and THEN provide a 'Maps' action to the relevant list.",
#             "   Example Response: 'Total Sales is $500. [Action: Maps(...)]'",
#             "5. PERMISSIONS: You inherit the user's permissions. Do not attempt restricted actions.",
#             "6. SCHEMAS: Always check valid fields in the Schema before Creating/Updating documents.",
#             "\nRESPONSE FORMAT:",
#             "   - If performing an action, output ONLY valid JSON: { \"action\": \"tool_name\", \"args\": { ... } }",
#             "   - If providing a final answer, just write clear text.",
#             "   - Do not output markdown code blocks for JSON if possible, but I will parse them if you do."
#         ]
        
#         return "\n".join(prompt)

#     def _call_llm(self, messages):
#         return completion(
#             model=self.config.get("model"),
#             messages=messages,
#             api_key=self.config.get("api_key"),
#             api_base=self.config.get("api_base")
#         )

#     def _parse_json(self, text):
#         """Robust JSON extraction"""
#         if not text: return None
        
#         # 1. Try extracting from code blocks first
#         if "```json" in text:
#             try:
#                 block = text.split("```json")[1].split("```")[0].strip()
#                 return json.loads(block)
#             except: pass
        
#         if "```" in text:
#              try:
#                 block = text.split("```")[1].split("```")[0].strip()
#                 return json.loads(block)
#              except: pass

#         # 2. Try finding raw JSON in text (brute force finder)
#         try:
#              start = text.find("{")
#              end = text.rfind("}")
#              if start != -1 and end != -1 and end > start:
#                  json_str = text[start:end+1]
#                  return json.loads(json_str)
#         except:
#              pass
             
#         return None
