import frappe
import json
import base64
import time
import traceback
from litellm import completion
from tb_owlai_core.utils import get_active_provider_config
from tb_owlai_core.tool_registry import ToolRegistry

# Conversation memory settings
CONTEXT_MESSAGE_LIMIT = 50  # Send last 50 messages to LLM


def get_or_create_conversation(conversation_id=None):
    """Get existing conversation or create a new one for current user"""
    user = frappe.session.user
    
    if conversation_id:
        # Load existing conversation
        try:
            conv = frappe.get_doc("OwlAI Conversation", conversation_id)
            # Check permission
            if not conv.has_permission("read"):
                frappe.throw("You don't have permission to access this conversation")
            return conv
        except frappe.DoesNotExistError:
            pass  # Will create new
    
    # Create new conversation
    conv = frappe.get_doc({
        "doctype": "OwlAI Conversation",
        "owner": user,
        "sharing_type": "Private",
        "status": "Active"
    })
    conv.insert(ignore_permissions=True)
    frappe.db.commit()
    return conv


def get_conversation_history(conversation, limit=CONTEXT_MESSAGE_LIMIT):
    """Load last N messages from a conversation for LLM context"""
    if not conversation.messages:
        return []
    
    # Get last N messages
    recent_messages = conversation.messages[-limit:] if len(conversation.messages) > limit else conversation.messages
    
    history = []
    for msg in recent_messages:
        if msg.role in ["user", "assistant"]:
            history.append({
                "role": msg.role,
                "content": msg.content
            })
    return history


def save_message(conversation, role, content, message_type="text", action_data=None):
    """Save a message to the conversation"""
    conversation.append("messages", {
        "role": role,
        "content": content[:100000] if content else "",  # Limit content size
        "message_type": message_type,
        "action_data": json.dumps(action_data) if action_data else None
    })
    conversation.message_count = len(conversation.messages)
    conversation.save(ignore_permissions=True)
    frappe.db.commit()


def get_doctype_from_route(route):
    """
    Extracts DocType from the current route.
    Route examples:
    - /app/todo -> Todo
    - /app/todo/TASK-001 -> Todo
    - /app/user-list -> User (via mapping or fuzzy match)
    """
    if not route: return None
    
    parts = route.strip("/").split("/")
    
    if len(parts) >= 2 and parts[0] == "app":
        doctype_slug = parts[1]
        if doctype_slug in ["query-report", "dashboard-view", "kanban-view"]:
             return None # Skip special views for now
             
        # Try to find DocType
        # 1. Direct Name Match
        if frappe.db.exists("DocType", doctype_slug):
            return doctype_slug
            
        # 2. Slug to Title (todo -> ToDo, system-settings -> System Settings)
        possible_name = doctype_slug.replace("-", " ").title()
        if frappe.db.exists("DocType", possible_name):
             return possible_name
        
        # 3. DB Search (case insensitive)
        try:
             dt = frappe.db.get_value("DocType", {"name": ["like", doctype_slug]}, "name")
             if dt: return dt
        except: pass
        
    return None

def get_schema_context(route):
    doctype = get_doctype_from_route(route)
    if not doctype:
        return ""
        
    try:
        meta = frappe.get_meta(doctype)
        fields = []
        # Basic Info
        schema_text = f"DocType: {doctype}\n"
        schema_text += f"Description: {meta.description or 'No description'}\n"
        
        # Fields
        schema_text += "Fields:\n"
        for df in meta.fields:
             if df.fieldtype not in ["Section Break", "Column Break", "Tab Break", "HTML", "Image", "Fold"]:
                 field_info = f"- {df.fieldname} ({df.fieldtype}): {df.label}"
                 if df.options:
                      field_info += f" [Options: {df.options}]"
                 if df.reqd:
                      field_info += " [Required]"
                 fields.append(field_info)
        
        schema_text += "\n".join(fields)
        
        return f"""
\n---
CONTEXT: USER IS CURRENTLY VIEWING DOCTYPE '{doctype}'.
SCHEMA INFORMATION:
{schema_text}
---
"""
    except Exception as e:
        # Don't fail the whole request if schema fetch fails
        print(f"Schema fetch error: {e}")
        return ""

def log_analytics(user, config, model, response_time, prompt_tokens, completion_tokens, total_tokens, status, tool_calls, full_prompt, full_response, error_message=None):
    """Log execution metrics to OwlAI Analytics if enabled"""
    try:
        settings = frappe.get_single("OwlAI Settings")
        if not settings.enable_analytics:
            return

        doc = frappe.get_doc({
            "doctype": "OwlAI Analytics",
            "user": user,
            "timestamp": frappe.utils.now(),
            "status": status,
            "provider": config.get("provider"),
            "model": model,
            "response_time": response_time,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "tool_calls": json.dumps(tool_calls, indent=2) if tool_calls else None,
            "full_prompt": json.dumps(full_prompt, indent=2) if full_prompt else str(full_prompt),
            "full_response": full_response,
            "error_message": error_message
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        print(f"Failed to log analytics: {e}")
        frappe.log_error("OwlAI Analytics Log Error")


@frappe.whitelist()
def handle_input_v2(route=None, text=None, conversation_id=None):
    """
    Main chat handler with conversation memory and Plugin System (ToolRegistry).
    """
    start_time = time.time()
    user = frappe.session.user
    roles = frappe.get_roles(user)
    
    # 2. Get AI Provider Config
    config = get_active_provider_config()
    if not config:
        return {"reply": "⚠️ AI Assistant is disabled or not configured. Please check 'OwlAI Settings'."}
    
    # 3. Get or create conversation
    conversation = get_or_create_conversation(conversation_id)
    if route:
        conversation.context_route = route
        conversation.save(ignore_permissions=True)
    
    # 4. Handle Files
    files = frappe.request.files
    image_file = files.get('image')
    audio_file = files.get('audio')

    # 5. Build System Prompt with Dynamic Tools & Schema Context
    registry = ToolRegistry()
    available_tools = registry.get_available_tools()
    
    schema_context = get_schema_context(route)
    
    system_prompt = f"""
    You are OwlAI, the Native Intelligence Layer for this Frappe/ERPNext system.
    User: {user} | Roles: {roles} | Current Route: {route}
    {schema_context}
    
    Your Goal: Assist the user by executing tools to interact with the system.
    
    Available Tools:
    {json.dumps(available_tools, indent=2)}

    Rules:
    1. To take an action, you MUST return a strict JSON object.
    2. Format: {{ "action": "tool_name", "args": {{ ... arguments ... }} }}
    3. If multiple actions are needed, you can return a list of objects used strictly for reasoning, but perform one action at a time preferably or use a 'pipeline' tool if available. For now, return ONE action object.
    4. If the user asks for a specific document or data, LOOK AT THE SCHEMA ABOVE to know field names.
    5. If just chatting or answering a question, reply with plain text.
    6. Do NOT wrap JSON in markdown blocks like ```json ... ``` if possible, but if you do, I will parse it.
    7. Be concise and professional.
    """

    # 6. Build messages with conversation history
    messages = [{"role": "system", "content": system_prompt}]
    history = get_conversation_history(conversation)
    messages.extend(history)
    
    # 7. Build current user message
    user_content = []
    user_text_for_storage = text or ""
    
    if text:
        user_content.append({"type": "text", "text": text})

    if image_file:
        image_bytes = image_file.read()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
        })
        user_text_for_storage = f"[Image Attached] {text or 'Analyze this image'}"

    if audio_file:
         user_text_for_storage = f"[Audio Attached] {text or 'Voice command'}"

    if user_content:
        messages.append({"role": "user", "content": user_content})
        save_message(conversation, "user", user_text_for_storage, 
                    message_type="image" if image_file else "text")
    else:
        if not audio_file:
             return {"reply": "I didn't receive any input.", "conversation_id": conversation.name}

    # Analytics Vars
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    full_response_text = ""
    tool_calls_log = []
    status = "Subject"
    
    try:
        # 8. Call AI
        response = completion(
            model=config.get("model"),
            messages=messages,
            api_key=config.get("api_key"),
            api_base=config.get("api_base")
        )
        
        if not response or not hasattr(response, 'choices') or not response.choices:
            raise Exception("Empty response from AI provider")

        reply_content = response.choices[0].message.content
        full_response_text = reply_content
        
        # Extract Token Usage (if available)
        if hasattr(response, 'usage'):
             prompt_tokens = response.usage.prompt_tokens
             completion_tokens = response.usage.completion_tokens
             total_tokens = response.usage.total_tokens
        
        # 9. Parse JSON Action
        action_data = None
        if reply_content:
            # Try parsing
            clean_content = reply_content.strip()
            # Handle markdown code blocks
            if "```json" in clean_content:
                clean_content = clean_content.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_content:
                clean_content = clean_content.split("```")[1].split("```")[0].strip()
            
            # Attempt JSON load
            if clean_content.startswith("{") or clean_content.startswith("["):
                try: 
                    action_data = json.loads(clean_content)
                    if isinstance(action_data, list) and len(action_data) > 0:
                        action_data = action_data[0] # Take first one
                except: 
                    pass
        else:
            reply_content = ""
        
        # 10. Execute Tools via Registry
        final_reply = reply_content
        response_payload = {"reply": final_reply, "conversation_id": conversation.name}

        if action_data and isinstance(action_data, dict) and "action" in action_data:
            tool_name = action_data.get("action")
            tool_args = action_data.get("args") or action_data.get("data") or action_data
            
            # Clean args
            if "action" in tool_args: del tool_args["action"]
            if "args" in tool_args: del tool_args["args"]

            tool_calls_log.append({"name": tool_name, "args": tool_args})

            # Execute Tool!
            result = registry.execute_tool(tool_name, tool_args)
            
            # Handle Tool Result
            if isinstance(result, dict):
                if "action" in result:
                    response_payload.update(result)
                    if "message" in result:
                        final_reply = result["message"]
                        response_payload["reply"] = final_reply
                elif "error" in result:
                    final_reply = f"Tool Error: {result.get('error')}"
                    response_payload["reply"] = final_reply
                    status = "Error"
                else:
                    final_reply = json.dumps(result, indent=2)
            else:
                 final_reply = str(result)
            
            # Update reply if it changed
            response_payload["reply"] = final_reply

        # 11. Save and Return
        save_message(conversation, "assistant", final_reply, 
                    message_type="action" if action_data else "text",
                    action_data=action_data)
        
        end_time = time.time()
        log_analytics(
            user=user,
            config=config,
            model=config.get("model"),
            response_time=round(end_time - start_time, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            status="Success" if status != "Error" else "Error",
            tool_calls=tool_calls_log,
            full_prompt=messages, # Log full context messages
            full_response=full_response_text
        )
        
        return response_payload

    except Exception as e:
        end_time = time.time()
        frappe.log_error(f"OwlAI Error ({config.get('provider')})")
        log_analytics(
            user=user,
            config=config,
            model=config.get("model"),
            response_time=round(end_time - start_time, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            status="Error",
            tool_calls=tool_calls_log,
            full_prompt=messages,
            full_response=full_response_text,
            error_message=str(e) + "\n" + traceback.format_exc()
        )
        return {"reply": f"Error interacting with AI: {str(e)}", "conversation_id": conversation.name}


@frappe.whitelist()
def update_owlai_settings(model=None, api_key=None):
    """Update settings directly from Chat UI"""
    if not frappe.session.user: return
    settings = frappe.get_single("OwlAI Settings")
    if model:
        if "gemini" in model.lower():
             settings.gemini_model = model
             settings.provider = "Generative AI (Gemini)"
    if api_key:
        settings.gemini_api_key = api_key
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success"}


@frappe.whitelist()
def get_conversations(limit=20):
    user = frappe.session.user
    return frappe.get_all("OwlAI Conversation",
        filters={"status": "Active"},
        or_filters=[["owner", "=", user], ["sharing_type", "=", "Public"]],
        fields=["name", "title", "modified"],
        order_by="modified desc",
        limit=limit
    )


@frappe.whitelist()
def new_conversation():
    conv = get_or_create_conversation()
    return {"conversation_id": conv.name}
