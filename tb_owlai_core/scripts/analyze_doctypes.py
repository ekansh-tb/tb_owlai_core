import frappe
from frappe.utils import get_link_to_form

def run():
    print("="*60)
    print("🧬 TB OwlAI Core - DocType & Data Integrity Analysis")
    print("="*60)

    # 1. Critical DocTypes Check
    doctypes = [
        "OwlAI Agent", "OwlAI Model", "OwlAI Provider", "OwlAI Tool", 
        "OwlAI Conversation", "OwlAI Message", "OwlAI Settings", 
        "OwlAI Knowledge Base", "OwlAI Analytics", "OwlAI Run"
    ]
    
    print(f"\n[1] Checking DocType Presence & Counts:")
    for dt in doctypes:
        try:
            count = frappe.db.count(dt)
            print(f"  ✅ {dt:<20}: {count} records")
        except Exception as e:
            print(f"  ❌ {dt:<20}: Schema Missing! ({e})")

    # 2. Critical Link Integrity
    print(f"\n[2] Checking Critical Links:")
    
    # Agents -> Models
    agents = frappe.get_all("OwlAI Agent", fields=["name", "model"])
    for agent in agents:
        if agent.model:
            if not frappe.db.exists("OwlAI Model", agent.model):
                 print(f"  ❌ Agent '{agent.name}' links to missing Model: '{agent.model}'")
            else:
                 print(f"  ✅ Agent '{agent.name}' -> Model '{agent.model}' (OK)")
        else:
            print(f"  ⚠️ Agent '{agent.name}' has NO Model selected")

    # Models -> Providers
    models = frappe.get_all("OwlAI Model", fields=["name", "provider"])
    for model in models:
        if model.provider:
            if not frappe.db.exists("OwlAI Provider", model.provider):
                 print(f"  ❌ Model '{model.name}' links to missing Provider: '{model.provider}'")
            else:
                 print(f"  ✅ Model '{model.name}' -> Provider '{model.provider}' (OK)")
        else:
            print(f"  ❌ Model '{model.name}' has NO Provider selected!")

    # 3. Settings Validation
    print(f"\n[3] Validating Settings:")
    settings = frappe.get_single("OwlAI Settings")
    
    print(f"  🔹 Default Agent: {settings.default_agent or 'None'}")
    if settings.default_agent and not frappe.db.exists("OwlAI Agent", settings.default_agent):
        print(f"    ❌ Default Agent '{settings.default_agent}' does not exist!")
        
    print(f"  🔹 Ollama Model: {settings.ollama_model or 'None'}")
    if settings.ollama_model and not frappe.db.exists("OwlAI Model", settings.ollama_model):
        print(f"    ❌ Ollama Model '{settings.ollama_model}' does not exist!")

    print(f"  🔹 Vision Model: {settings.vision_model or 'None'}")
    if settings.vision_model and not frappe.db.exists("OwlAI Model", settings.vision_model):
        print(f"    ❌ Vision Model '{settings.vision_model}' does not exist!")
        
    print(f"  🔹 Provider Strategy: {settings.provider}")
    
    # 4. Tool Registry Check
    print(f"\n[4] Inspecting Tool Registry:")
    tool_count = frappe.db.count("OwlAI Tool")
    print(f"  🔹 Registered Tools: {tool_count}")
    
    # Check if tools have schemas
    tools_no_schema = frappe.get_all("OwlAI Tool", filters={"args_schema": ["is", "not set"]}, fields=["name"])
    if tools_no_schema:
         print(f"  ⚠️ Tools missing schema: {[t.name for t in tools_no_schema]}")
    else:
         print(f"  ✅ All tools have schemas.")

    # 5. Conversation Analysis
    print(f"\n[5] Conversation Health:")
    conv_count = frappe.db.count("OwlAI Conversation")
    msg_count = frappe.db.count("OwlAI Message") # Child table usually accessed differently, but let's try direct count if valid doctype or sql
    
    # Message is a child table usually. Let's check SQL count for child table
    try:
        msg_count_sql = frappe.db.sql("select count(*) from `tabOwlAI Message`")[0][0]
        print(f"  🔹 Total Conversations: {conv_count}")
        print(f"  🔹 Total Messages: {msg_count_sql}")
    except:
        print("  ⚠️ Could not count messages (table might be missing)")

    print("\n✅ Analysis Complete.")
