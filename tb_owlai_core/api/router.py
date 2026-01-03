import frappe
import json
import base64
from litellm import completion
from tb_owlai_core.utils import get_active_provider_config

# Conversation memory settings
CONTEXT_MESSAGE_LIMIT = 20  # Send last 20 messages to LLM


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


# --- META TOOLS ---

def get_schema_info(doctype):
    """Meta-Tool: Get simplified schema for a DocType"""
    if not frappe.db.exists("DocType", doctype):
        return f"Error: DocType '{doctype}' does not exist."
    
    meta = frappe.get_meta(doctype)
    fields = []
    for df in meta.fields:
        if not df.hidden:
            fields.append(f"{df.fieldname} ({df.fieldtype}): {df.label}")
    
    return f"Schema for {doctype}:\n" + "\n".join(fields[:50]) # Limit to 50 fields to save tokens


def universal_search(doctype, query):
    """Meta-Tool: Search for documents"""
    try:
        results = frappe.db.get_list(doctype, 
            filters=None, # generic search
            fields=["name", "title", "status", "modified"],
            or_filters=[
                ["name", "like", f"%{query}%"],
                ["title", "like", f"%{query}%"]
            ] if query else None,
            limit=5
        )
        return results
    except Exception as e:
        return f"Error searching {doctype}: {str(e)}"


def run_report(report_name, filters=None):
    """Meta-Tool: Run a report and return summary"""
    try:
        import frappe.desk.query_report
        result = frappe.desk.query_report.run(report_name, filters=filters or {})
        
        columns = result.get("columns", [])
        data = result.get("result", [])
        
        if not data:
            return "Report ran successfully but returned no data."
            
        # Summerize if too large
        summary = f"Report '{report_name}' Results (First 5 rows):\n"
        # Simple CSV-like format for LLM
        headers = [c.get("label") for c in columns][:5] # limit columns
        summary += " | ".join(headers) + "\n"
        
        for row in data[:5]:
            # row can be dict or list
            if isinstance(row, dict):
                vals = [str(row.get(c.get("fieldname"))) for c in columns[:5]]
            else:
                vals = [str(v) for v in row][:5]
            summary += " | ".join(vals) + "\n"
            
        return summary
    except Exception as e:
        return f"Error running report: {str(e)}"


def perform_action(action_data):
    """Execute the decided action"""
    action = action_data.get("action")
    
    if action == "count":
        doctype = action_data.get("doctype")
        filters = action_data.get("filters", {})
        try:
            count = frappe.db.count(doctype, filters)
            return f"Found {count} {doctype}(s)."
        except Exception as e:
            return f"Error counting: {str(e)}"

    elif action == "get_schema":
        return get_schema_info(action_data.get("doctype"))

    elif action == "search":
        return universal_search(action_data.get("doctype"), action_data.get("query"))
        
    elif action == "report":
        return run_report(action_data.get("report_name"), action_data.get("filters"))

    return None # Client-side actions handled by frontend


@frappe.whitelist()
def handle_input_v2(route=None, text=None, conversation_id=None):
    """
    Main chat handler with conversation memory and Meta-Tools.
    """
    # 1. Capture Context
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
    
    # 4. Handle Files
    files = frappe.request.files
    image_file = files.get('image')
    audio_file = files.get('audio')

    # 5. Build System Prompt (NATIVE INTELLIGENCE)
    system_prompt = f"""
    You are OwlAI, the Native Intelligence Layer for this Frappe/ERPNext system.
    User: {user} | Roles: {roles} | Current Screen: {route}
    
    Your Goal: Assist the user by understanding their intent and using "Meta-Tools" to interact with the system.
    
    Available Actions (JSON Output):
    1. **Search**: Find documents.
       {{ "action": "search", "doctype": "Sales Invoice", "query": "Pending" }}
    2. **Schema**: specific details/fields of a Doctype.
       {{ "action": "get_schema", "doctype": "Item" }}
    3. **Create**: open a form to create a new document.
       {{ "action": "create_doc", "doctype": "ToDo", "data": {{ "description": "Call Mom" }} }}
    4. **Navigate**: Go to a list or report.
       {{ "action": "navigate", "doctype": "Leave Application", "view": "List" }}
    5. **Count**: Count records.
       {{ "action": "count", "doctype": "Customer", "filters": {{ "status": "Open" }} }}

    Rules:
    - If the user asks a question that requires data, use "search" or "count".
    - If the user wants to DO something, use "create_doc" or key actions.
    - If just chatting, reply with plain text.
    - Be concise and professional.
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
         # Simplified for now
         user_text_for_storage = f"[Audio Attached] {text or 'Voice command'}"

    if user_content:
        messages.append({"role": "user", "content": user_content})
        save_message(conversation, "user", user_text_for_storage, 
                    message_type="image" if image_file else "text")
    else:
        if not audio_file:
             return {"reply": "I didn't receive any input.", "conversation_id": conversation.name}

    try:
        # 8. Call AI
        response = completion(
            model=config.get("model"),
            messages=messages,
            api_key=config.get("api_key"),
            api_base=config.get("api_base")
        )
        
        reply_content = response.choices[0].message.content
        
        # 9. Parse JSON Action
        action_data = None
        if "```json" in reply_content:
            json_str = reply_content.split("```json")[1].split("```")[0].strip()
            try: action_data = json.loads(json_str)
            except: pass
        elif reply_content.strip().startswith("{") and reply_content.strip().endswith("}"):
            try: action_data = json.loads(reply_content)
            except: pass
        
        # 10. Execute Backend Meta-Tools
        final_reply = reply_content
        if action_data:
            # Execute backend-side actions immediately for "Agentic" feel
            result = perform_action(action_data)
            if result:
                # If we got a result (like count or schema), we might want to return it 
                # OR (Better for now) return it as the reply context
                final_reply = str(result)
                # If it was a search, return the data to frontend to render nicely
                if action_data.get("action") == "search":
                     return {
                         "reply": f"Found these results for **{action_data.get('doctype')}**:",
                         "action": "list", # New Frontend Action
                         "data": result,
                         "conversation_id": conversation.name
                     }

        # 11. Save and Return
        save_message(conversation, "assistant", final_reply, 
                    message_type="action" if action_data else "text",
                    action_data=action_data)
        
        if action_data and action_data.get("action") in ["create_doc", "navigate"]:
            action_data["conversation_id"] = conversation.name
            return action_data

        return {"reply": final_reply, "conversation_id": conversation.name}

    except Exception as e:
        frappe.log_error(f"OwlAI Error ({config.get('provider')})")
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
