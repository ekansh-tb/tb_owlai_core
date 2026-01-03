import frappe
import json
import base64
from litellm import completion

@frappe.whitelist()
def handle_input_v2(route=None, text=None):
    # 1. Capture Context
    user = frappe.session.user
    roles = frappe.get_roles(user)
    
    # 2. Handle Files (Audio/Image) from Request
    # Frappe puts uploaded files in frappe.request.files
    files = frappe.request.files
    image_file = files.get('image')
    audio_file = files.get('audio')

    # 3. Build System Prompt
    system_prompt = f"""
    You are the AI Assistant for this Company (Powered by Frappe).
    User: {user} | Roles: {roles} | Current Page: {route}
    
    Your Capabilities:
    1. **Chat**: Answer questions about the system, python, or general topics.
    2. **Action**: If the user asks to DO something (Create, Delete, Navigate), return a JSON action.
    
    Output Format:
    - If Chatting: Return a friendly plain text response (Markdown supported).
    - If Performing Action: Return ONLY a JSON object:
      {{
         "action": "create_doc",
         "doctype": "ToDo", 
         "data": {{ "description": "..." }}
      }}
      
    Examples:
    - "Create a task to buy milk" -> {{ "action": "create_doc", "doctype": "ToDo", "data": {{ "description": "Buy milk" }} }}
    - "Who are you?" -> "I am OwlAI, your assistant."
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
    # Note: Audio handling depends on model support. 
    # For now, we assume Gemini 1.5 Pro/Flash handling via simple prompt or future multimodal support.
    # If using a model that DOESN'T support audio, we would need STT here.
    # Let's try to pass it as a file/image part for Gemini (it treats them similarly in API) or just warn.
    if audio_file:
        audio_bytes = audio_file.read()
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        user_content.append({
            "type": "image_url", # Litellm/Gemini often use this key for generic inline data, or 'image_url' with audio mime type works in some adapters.
            # Best practice for Litellm generic:
            "image_url": {"url": f"data:audio/wav;base64,{audio_b64}"}
        })
        user_content.append({"type": "text", "text": "This is a voice command from the user. Listen to it and execute the request."})

    # If we have content, add to messages
    if user_content:
        messages.append({"role": "user", "content": user_content})
    else:
        # Fallback if only audio was provided but we couldn't process it yet?
        # If text is empty and image is empty, but audio exists
        if audio_file:
             # If we can't handle audio, return an error
             return {"message": {"reply": "🎤 Voice processing is coming soon! (Backend pending)"}}
        if not text and not image_file:
             return {"message": {"reply": "I didn't receive any input."}}

    try:
        response = completion(
            model=frappe.conf.get("owlai_model") or "gemini/gemini-1.5-pro",
            messages=messages,
            api_key=frappe.conf.get("GEMINI_API_KEY")
        )
        
        reply_content = response.choices[0].message.content
        
        # Parse JSON if it looks like JSON
        if "```json" in reply_content:
            json_str = reply_content.split("```json")[1].split("```")[0].strip()
            action_data = json.loads(json_str)
            return {"message": action_data}
        elif reply_content.strip().startswith("{") and reply_content.strip().endswith("}"):
             # Try pure JSON
            try:
                action_data = json.loads(reply_content)
                return {"message": action_data}
            except:
                pass

        return {"message": {"reply": reply_content}}

    except Exception as e:
        frappe.log_error("OwlAI Error")
        return {"message": {"reply": f"Error interacting with AI: {str(e)}"}}
