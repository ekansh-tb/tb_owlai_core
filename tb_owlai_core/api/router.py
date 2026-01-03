import frappe
import json
import base64
from litellm import completion
from tb_owlai_core.utils import get_active_provider_config

@frappe.whitelist()
def handle_input_v2(route=None, text=None):
    # 1. Capture Context
    user = frappe.session.user
    roles = frappe.get_roles(user)
    
    # 2. Get AI Provider Config
    config = get_active_provider_config()
    if not config:
        return {"reply": "⚠️ AI Assistant is disabled or not configured. Please check 'OwlAI Settings'."}
    
    # 3. Handle Files (Audio/Image) from Request
    files = frappe.request.files
    image_file = files.get('image')
    audio_file = files.get('audio')

    # 4. Build System Prompt
    system_prompt = f"""
    You are the AI Assistant for this Company (Powered by Frappe).
    User: {user} | Roles: {roles} | Current Page: {route}
    
    Your Capabilities:
    1. **Chat**: Answer questions about the system, python, or general topics.
    2. **Action**: If the user asks to DO something (Create, Delete, Navigate), return a JSON action.
    3. **Query**: If the user asks "How many..." or "Count...", return a "count" action.
    
    Output Format:
    - If Chatting: Return a friendly plain text response (Markdown supported).
    - If Performing Action: Return ONLY a JSON object:
      {{
         "action": "create_doc",
         "doctype": "ToDo", 
         "data": {{ "description": "..." }}
      }}
      OR
      {{
         "action": "navigate",
         "doctype": "Sales Order",
         "view": "List"
      }}
      OR
      {{
         "action": "count",
         "doctype": "Warehouse",
         "filters": {{}} 
      }}

    Rules for DocType Inference:
    - Use your knowledge of ERPNext/Frappe DocTypes to infer specific names.
    - Examples: "Clients" -> "Customer", "Bill" -> "Purchase Invoice" or "Sales Invoice", "Item" -> "Item", "Staff" -> "Employee".

    Examples:
    - "Create a task to buy milk" -> {{ "action": "create_doc", "doctype": "ToDo", "data": {{ "description": "Buy milk" }} }}
    - "Go to Sales Orders" -> {{ "action": "navigate", "doctype": "Sales Order", "view": "List" }}
    - "Open List of Customers" -> {{ "action": "navigate", "doctype": "Customer", "view": "List" }}
    - "Who are you?" -> "I am OwlAI, your assistant."
    - "How many users are there?" -> {{ "action": "count", "doctype": "User", "filters": {{}} }}
    - (Image of Invoice) -> {{ "action": "create_doc", "doctype": "Purchase Invoice", "data": {{ ...extracted fields... }} }}
    """

    messages = [{"role": "system", "content": system_prompt}]
    
    user_content = []
    
    # Add Text
    if text:
        user_content.append({"type": "text", "text": text})

    # Add Image
    if image_file:
        image_bytes = image_file.read()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
        })
        user_content.append({"type": "text", "text": "Analyze this image and perform the relevant action or describe it."})

    # Add Audio
    if audio_file:
        audio_bytes = audio_file.read()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:audio/wav;base64,{audio_b64}"}
        })
        user_content.append({"type": "text", "text": "This is a voice command from the user. Listen to it and execute the request."})

    # If we have content, add to messages
    if user_content:
        messages.append({"role": "user", "content": user_content})
    else:
        if audio_file:
             return {"reply": "🎤 Audio context received."}
        if not text and not image_file:
             return {"reply": "I didn't receive any input."}

    try:
        # 5. Call AI with Dynamic Config
        try:
            response = completion(
                model=config.get("model"),
                messages=messages,
                api_key=config.get("api_key"),
                api_base=config.get("api_base") # Optional, for Ollama
            )
        except Exception as ai_error:
             error_msg = str(ai_error)
             if "404" in error_msg and "not found" in error_msg:
                 return {"reply": f"⚠️ Model Error: The model '{config.get('model')}' was not found. Please check your API Key and Model Name in 'OwlAI Settings'."}
             if "401" in error_msg:
                 return {"reply": "⚠️ Authentication Error: Invalid API Key. Please check 'OwlAI Settings'."}
             raise ai_error
        
        reply_content = response.choices[0].message.content
        
        # Parse JSON if it looks like JSON
        action_data = None
        if "```json" in reply_content:
            json_str = reply_content.split("```json")[1].split("```")[0].strip()
            action_data = json.loads(json_str)
        elif reply_content.strip().startswith("{") and reply_content.strip().endswith("}"):
             # Try pure JSON
            try:
                action_data = json.loads(reply_content)
            except:
                pass
        
        if action_data:
            # Handle Backend Actions (e.g. Count)
            if action_data.get("action") == "count":
                doctype = action_data.get("doctype")
                filters = action_data.get("filters", {})
                try:
                    count = frappe.db.count(doctype, filters)
                    return {"reply": f"OwlAI: I found **{count}** {doctype}(s)."}
                except Exception as db_err:
                    return {"reply": f"⚠️ DB Error: Could not count {doctype}. Details: {str(db_err)}"}
            
            # Return other actions to Frontend (create_doc, etc)
            return action_data

        return {"reply": reply_content}

        return {"reply": reply_content}

    except Exception as e:
        frappe.log_error(f"OwlAI Error ({config.get('provider')})")
        return {"reply": f"Error interacting with AI ({config.get('provider')}): {str(e)}"}
