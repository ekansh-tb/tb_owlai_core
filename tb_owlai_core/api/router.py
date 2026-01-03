import frappe
import json
from litellm import completion

@frappe.whitelist()
def handle_input(file_url=None, text_query=None, current_route=None):
    # 1. Capture Context
    user = frappe.session.user
    roles = frappe.get_roles(user)
    
    # 2. Build System Prompt
    system_prompt = f"""
    You are the Operating System for this Company.
    User Context: {{ "user": "{user}", "roles": {json.dumps(roles)}, "current_page": "{current_route}" }}
    
    Your Goal: Analyze the input (Text or Image content) and decide the ONE best action.
    
    Scenarios:
    - If User is 'Purchase Manager' & Input is Bill/Invoice -> Action: Create 'Purchase Invoice'.
    - If User is 'Sales User' & Input is Bill/Receipt -> Action: Create 'Expense Claim'.
    - If Input is voice "Paid 500 to Vendor" -> Action: Create 'Payment Entry'.
    - If Input is generic like "Sales Order", "New Invoice" -> Action: Create relevant DocType with empty data.
    
    Output Format: Return ONLY raw JSON (no markdown):
    {{
        "action": "create_doc",
        "doctype": "Target DocType Name",
        "data": {{ ...field_name: value... }}
    }}
    """

    # 3. Prepare Message for AI
    messages = [{"role": "system", "content": system_prompt}]
    
    user_content = []
    if text_query:
        user_content.append({"type": "text", "text": text_query})
    
    if file_url:
        # In a real scenario, we would base64 encode the file here. 
        # For now, pass the URL context to the LLM.
        user_content.append({"type": "text", "text": f"User uploaded an image file at: {file_url}. Analyze its visual content as a document."})

    messages.append({"role": "user", "content": user_content})

    # 4. Call AI (Relies on site_config for keys)
    # Uses Gemini by default, but litellm supports switching to Ollama easily
    response = completion(
        model=frappe.conf.get("owlai_model") or "gemini/gemini-2.5-flash-lite", 
        messages=messages,
        api_key=frappe.conf.get("GEMINI_API_KEY")
    )
    
    content = response.choices[0].message.content
    # Clean up markdown if present
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
        
    return json.loads(content)
