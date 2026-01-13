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
    def __init__(self, user: str, context: Optional[Any] = None, conversation: Any = None, conversation_name: Optional[str] = None, max_steps: int = 5, agent_id: str = None):
        self.user = user
        self.context = context
        self.max_steps = max_steps
        self.registry = ToolRegistry()
        self.agent_id = agent_id
        self.agent_doc = None
        
        # Load Agent Document
        if self.agent_id:
            if frappe.db.exists("OwlAI Agent", self.agent_id):
                self.agent_doc = frappe.get_doc("OwlAI Agent", self.agent_id)
        
        # Fallback to default agent from settings if not provided
        if not self.agent_doc:
            settings = frappe.get_single("OwlAI Settings")
            if hasattr(settings, "default_agent") and settings.default_agent:
                self.agent_doc = frappe.get_doc("OwlAI Agent", settings.default_agent)

        self.config = self._resolve_config()
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

    def _resolve_config(self) -> Dict[str, Any]:
        """
        Resolves the LLM configuration (Model, Provider, API Key).
        Priority: OwlAI Agent -> OwlAI Settings (Fallback/Legacy)
        """
        if self.agent_doc and self.agent_doc.model:
            try:
                model_doc = frappe.get_doc("OwlAI Model", self.agent_doc.model)
                provider_doc = frappe.get_doc("OwlAI Provider", model_doc.provider)
                
                # Construct config from new DocTypes
                config = {
                    "model": f"{provider_doc.provider_name.lower()}/{model_doc.model_name}", # litellm format assumption
                    "model_doc_name": model_doc.name,
                    "api_key": provider_doc.get_password("api_key", raise_exception=False),
                    "api_base": provider_doc.api_base,
                    "provider": provider_doc.provider_name.lower()
                }
                
                # adjustments for specific providers if needed
                if config["provider"] == "ollama":
                     # config["model"] is already set to "ollama/{model_name}" by default logic
                     if not config["api_base"]:
                         config["api_base"] = "http://localhost:11434"
                
                return config
            except Exception as e:
                frappe.log_error(f"Error resolving OwlAI Agent config: {e}")
        
        # Fallback to legacy settings-based config
        return get_active_provider_config()

    def _get_allowed_tools(self) -> List[Dict[str, Any]]:
        """
        Returns the list of tool schemas allowed for this agent.
        """
        all_tools = self.registry.get_tools_schema()
        
        if not self.agent_doc or not self.agent_doc.tools:
            return all_tools
            
        # Filter based on OwlAI Agent Tool table
        enabled_tool_names = [row.tool for row in self.agent_doc.tools if row.enabled]
        
        # Map tool names to schema. Handle potential name mismatch if registry uses class name vs ID.
        # Currently registry.get_tools_schema returns list of dicts with 'name' key.
        return [tool for tool in all_tools if tool["name"] in enabled_tool_names]

    def _load_history(self):
        """Loads conversation history into LLM format with token management."""
        if not self.conversation or not self.conversation.messages:
            return
            
        # Load all messages first
        limit = 50 # Load more initially, then trim
        msgs = self.conversation.messages[-limit:]
        
        temp_history = []
        for m in msgs:
            role = m.role
            # Observations are saved as 'system' but fed as 'user' or 'tool' (if supported)
            if role == "system":
                role = "user"
            
            if role in ["user", "assistant", "system"]:  # Simplified roles
                temp_history.append({
                    "role": role,
                    "content": m.content
                })
        
        # Trim history to fit token limit (heuristic: ~4 chars per token)
        self.history = self._trim_history(temp_history)

    def _trim_history(self, history: List[Dict[str, str]], max_tokens: int = 6000) -> List[Dict[str, str]]:
        """
        Trims message history to approximate token limit.
        Keeps system prompt implicitly (as it's added later) but trims variable history.
        Strategies:
        1. Keep most recent messages.
        2. Always keep the first User message (optional, but good for context).
        """
        current_chars = 0
        allowed_chars = max_tokens * 4
        
        trimmed = []
        # Reverse iterate to keep most recent
        for msg in reversed(history):
            msg_len = len(msg.get("content", ""))
            if current_chars + msg_len > allowed_chars:
                break
            trimmed.insert(0, msg)
            current_chars += msg_len
            
        return trimmed

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
        tools = self._get_allowed_tools()
        
        # Base Prompt
        base_instruction = "You are OwlAI, the Native Intelligence Layer for Frappe/ERPNext."
        if self.agent_doc and self.agent_doc.system_prompt:
             base_instruction = self.agent_doc.system_prompt

        prompt = [
            base_instruction,
            f"Acting User: {self.user}",
            f"Current Time: {frappe.utils.now()}",
            # Dynamic Context Injection
            self.context.get_full_context_string() if self.context and hasattr(self.context, "get_full_context_string") else "",
            "\nCORE RULES:",
            "1. PLAN FIRST: If the user wants to CREATE or UPDATE a document, Step 1 is ALWAYS `get_doctype_info` to check mandatory fields.",
            "2. NO HALLUCINATION: You MUST know the schema (fieldnames, 'reqd' status) before calling `create_document`.",
            "3. ACTION-ORIENTED: Use tools to inspect, create, or update data.",
            "4. RESPONSE FORMAT: Brief reasoning text, followed by JSON: \nReasoning...\n```json\n{ \"action\": \"tool_name\", \"args\": { ... } }\n```",
            "5. ERROR RECOVERY: If a tool fails with 'missing fields', immediately call `get_doctype_info`.",
            "\nAVAILABLE TOOLS:",
            json.dumps(tools, indent=2),
            "\nIMPORTANT: Output ONLY the reasoning and the JSON block."
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
        
        tool_call = None
        thought_content = text

        # 1. Try extracting from code blocks first
        json_pattern = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
        match = json_pattern.search(text)
        
        if match:
            json_str = match.group(1)
            try:
                data = json.loads(json_str)
                if "action" in data:
                    tool_call = {"tool": data["action"], "args": data.get("args", {})}
                    thought_content = text.replace(match.group(0), "").strip()
            except json.JSONDecodeError:
                pass

        # 2. Try finding raw JSON object if no code block success
        if not tool_call:
            try:
                # Find the LAST occurrence of { "action": ... } pattern to avoid false positives in thought
                # This is a bit risky but standard models output JSON last
                candidate_jsons = re.findall(r"(\{.*\"action\".*\})", text, re.DOTALL)
                for json_candidate in reversed(candidate_jsons):
                    try:
                        data = json.loads(json_candidate)
                        if "action" in data:
                            tool_call = {"tool": data["action"], "args": data.get("args", {})}
                            thought_content = text.replace(json_candidate, "").strip()
                            break
                    except: continue
            except: pass
        
        # 3. Simple cleanup if thought content is empty but logic implies thought
        if not thought_content and not tool_call:
             thought_content = text

        if tool_call:
             return {
                "type": "tool_call",
                "tool": tool_call["tool"], 
                "args": tool_call["args"],
                "content": thought_content
             }
         
        return {"type": "text", "content": text}
        
        if tool_call:
            return {
                "type": "tool_call", 
                "tool": tool_call["tool"], 
                "args": tool_call["args"],
                "content": thought_content # Return the thought/reasoning
            }
        
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
        
        # Initialize Run Log
        run_doc = None
        start_time = time.time()
        
        try:
            if self.conversation:
                run_doc = frappe.get_doc({
                    "doctype": "OwlAI Run",
                    "thread": self.conversation.name,
                    "agent": self.agent_doc.name if self.agent_doc else None,
                    "status": "Running",
                    "start_time": frappe.utils.now()
                })
                run_doc.insert(ignore_permissions=True)
                frappe.db.commit()
                
        except Exception as e:
            frappe.logger("owlai").error(f"Failed to create Run Log: {e}")

        try:
            while current_step < self.max_steps:
                current_step += 1
                
                try:
                    settings = frappe.get_single("OwlAI Settings")
                    temperature =  settings.response_temperature if settings.response_temperature is not None else 0.7
                    
                    # Caching logic
                    caching = False
                    cache_params = None
                    if settings.enable_caching:
                        caching = True
                        cache_params = {
                            "type": "redis",
                            "host": "localhost",
                            "port": 6379,
                            "ttl": settings.cache_ttl or 300
                        }

                    response = completion(
                        model=self.config.get("model"),
                        messages=messages,
                        api_key=self.config.get("api_key"),
                        api_base=self.config.get("api_base"),
                        temperature=temperature,
                        caching=caching,
                        cache_params=cache_params,
                        stop=["\nObservation:", "Observation:", "User:", "Note:"]
                    )
                    
                    # Track Token Usage
                    if hasattr(response, 'usage'):
                        self.stats["prompt_tokens"] += response.usage.prompt_tokens
                        self.stats["completion_tokens"] += response.usage.completion_tokens
                        self.stats["total_tokens"] += response.usage.total_tokens
                        # TODO: Save stats to Agent Run doctype if implemented

                except Exception as e:
                    return {"reply": f"LLM Connection Error: {str(e)}", "close_chat": False}

                raw_content = response.choices[0].message.content or ""
                parsed = self._parse_llm_response(raw_content)

                if parsed["type"] == "tool_call":
                    tool_name = parsed["tool"]
                    tool_args = parsed["args"]
                    thought_text = parsed.get("content")

                    self.stats["tool_calls"].append({"tool": tool_name, "args": tool_args})
                    
                    try:
                        # Save Reasoning if present
                        if thought_text:
                            self.save_message("assistant", thought_text)
                            messages.append({"role": "assistant", "content": thought_text})

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

            # Finalize Run Log
            if run_doc:
                try:
                    run_doc.reload()
                    run_doc.status = "Completed"
                    run_doc.end_time = frappe.utils.now()
                    run_doc.duration = time.time() - start_time
                    run_doc.total_tokens = self.stats["total_tokens"]
                    run_doc.prompt_tokens = self.stats["prompt_tokens"]
                    run_doc.completion_tokens = self.stats["completion_tokens"]
                    run_doc.save(ignore_permissions=True)
                    frappe.db.commit()
                except Exception as e:
                    frappe.logger("owlai").error(f"Failed to update Run Log: {e}")
                
            return response_data
        
        except Exception as e:
            # Catch top-level errors in the loop
            if run_doc:
                try:
                    run_doc.reload()
                    run_doc.status = "Failed"
                    run_doc.error_message = str(e)
                    run_doc.save(ignore_permissions=True)
                    frappe.db.commit()
                except: pass
            
            # Re-raise or return error reply
            frappe.log_error(f"Agent Run Error: {e}")
            return {"reply": f"An error occurred during agent execution: {str(e)}", "close_chat": False}