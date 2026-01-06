import frappe
import json
import base64
import time
import traceback
from litellm import completion
from tb_owlai_core.utils import get_active_provider_config
from tb_owlai_core.tool_registry import ToolRegistry
from tb_owlai_core.owlai_core.agent import OwlAgent
from tb_owlai_core.utils.context import OwlContext

# Conversation memory settings are now in OwlAI Settings

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


def get_conversation_history(conversation, limit=None):
    """Load last N messages from a conversation for LLM context"""
    if not conversation.messages:
        return []
    
    if limit is None:
        settings = frappe.get_single("OwlAI Settings")
        limit = settings.context_message_limit or 20

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
def handle_input_v2(route=None, text=None, conversation_id=None, context=None):
    """
    Main chat handler using the new Agent Architecture.
    Accepts:
    - route: Current route string (legacy, also in context)
    - text: User query
    - conversation_id: ID to continue
    - context: JSON string containing frontend context (form_data, selection, etc.)
    """
    user = frappe.session.user
    
    # 1. Get AI Provider Config
    config = get_active_provider_config()
    if not config:
        return {"reply": "⚠️ AI Assistant is disabled or not configured. Please check 'OwlAI Settings'."}
    
    # 2. Get or create conversation
    conversation = get_or_create_conversation(conversation_id)
    if route and not conversation.context_route:
        conversation.context_route = route
        conversation.save(ignore_permissions=True)
    
    # 3. Handle Files
    files = frappe.request.files
    image_file = files.get('image')
    audio_file = files.get('audio')
    
    # Update Title if needed
    _update_conversation_title(conversation, text, image_file, audio_file)

    # 4. Prepare Context
    context_data = {}
    if context:
        try:
             context_data = json.loads(context)
        except: pass
    
    # If route is passed separately, prefer it or fallback to context
    current_route = route or context_data.get('route')
    
    agent_context = OwlContext(
        route=current_route,
        form_data=context_data.get('form_data'),
        selected_items=context_data.get('selected_items')
    )
    
    # 5. Instantiate and Run Agent
    settings = frappe.get_single("OwlAI Settings")
    max_steps = settings.max_agent_loops or 5
    
    agent = OwlAgent(user=user, context=agent_context, conversation=conversation, max_steps=max_steps)
    
    start_time = time.time()
    status = "Success"
    error_message = None
    result = {}
    
    try:
        result = agent.run(text, image_file, audio_file)
    except Exception as e:
        status = "Error"
        error_message = str(traceback.format_exc())
        frappe.log_error("OwlAI Agent Error")
        result = {"reply": f"An error occurred: {str(e)}"}
    finally:
        end_time = time.time()
        duration = end_time - start_time
        
        stats = result.get("stats", {})
        messages = result.get("messages", [])
        
        # Log Analytics
        try:
             log_analytics(
                user=user,
                config=config,
                model=config.get("model"),
                response_time=duration,
                prompt_tokens=stats.get("prompt_tokens", 0),
                completion_tokens=stats.get("completion_tokens", 0),
                total_tokens=stats.get("total_tokens", 0),
                status=status,
                tool_calls=stats.get("tool_calls", []),
                full_prompt=messages if messages else text,
                full_response=result.get("message", ""),
                error_message=error_message
            )
        except Exception as log_e:
             print(f"Analytics Error: {log_e}")

    
    # result contains {"reply": "..."} coming from agent.run()
    # Add conversation_id for frontend tracking
    result["conversation_id"] = conversation.name
    
    return result

def _update_conversation_title(conversation, text, image_file, audio_file):
    """Helper to name the conversation"""
    title_text = text or ""
    if not title_text.strip():
        if image_file: title_text = "Image Analysis"
        elif audio_file: title_text = "Voice Command"
    
    if title_text and (not conversation.title or conversation.title.startswith("Conversation ")):
        title = title_text[:50] + "..." if len(title_text) > 50 else title_text
        conversation.title = title
        conversation.save(ignore_permissions=True)


@frappe.whitelist()
def update_owlai_settings(model=None, api_key=None, enable_analytics=None):
    """Update settings directly from Chat UI"""
    if not frappe.session.user: return
    settings = frappe.get_single("OwlAI Settings")
    if model:
        if "gemini" in model.lower():
             settings.gemini_model = model
             settings.provider = "Generative AI (Gemini)"
    if api_key:
        settings.gemini_api_key = api_key
    
    if enable_analytics is not None:
        settings.enable_analytics = int(enable_analytics)

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


@frappe.whitelist()
def get_conversation_messages(conversation_id):
    if not conversation_id: return []
    try:
        conv = frappe.get_doc("OwlAI Conversation", conversation_id)
        if not conv.has_permission("read"): return []
        
        messages = []
        for m in conv.messages:
            try:
                action_data = json.loads(m.action_data) if m.action_data else None
            except:
                action_data = None

            messages.append({
                "role": m.role,
                "content": m.content,
                "message_type": m.message_type,
                "creation": m.creation,
                "idx": m.idx,
                "action_data": action_data
            })
        return messages
    except:
        return []
