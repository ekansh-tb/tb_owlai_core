import frappe
import requests
from tb_owlai_core.tool_registry import ToolRegistry

def setup_all_defaults():
    """
    Sets up default Providers, Models, Agents, Tools and Settings.
    Safe to run multiple times (idempotent).
    """
    setup_tools()
    provider_doc_name = setup_provider_and_model()
    setup_default_agent(provider_doc_name)
    frappe.db.commit()

def setup_tools():
    # Sync Tools
    registry = ToolRegistry()
    registry._sync_tools()

def check_ollama_service():
    """Checks if Ollama is running on localhost:11434"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return False

def setup_provider_and_model():
    # 2. Setup Provider & Model
    # Logic: Check if Ollama is running. If so, configure Ollama. Else, configure OpenAI placeholder.
    
    ollama_data = check_ollama_service()
    
    if ollama_data:
        return setup_ollama(ollama_data)
    else:
        # Fallback to OpenAI if Ollama isn't found
        # But first, check if we already have a default provider set. If yes, respect it.
        default_provider = frappe.db.get_value("OwlAI Provider", {"is_default": 1}, "name")
        if default_provider:
            return default_provider
        return setup_openai()

def setup_ollama(ollama_data=None):
    # Provider: Ollama
    existing_provider = frappe.db.get_value("OwlAI Provider", {"provider_name": "Ollama"}, "name")
    
    if existing_provider:
        provider_doc_name = existing_provider
    else:
        p = frappe.get_doc({
            "doctype": "OwlAI Provider",
            "provider_name": "Ollama",
            "api_base": "http://localhost:11434",
            "is_default": 1
        })
        p.insert(ignore_permissions=True)
        provider_doc_name = p.name
    
    # Process dynamically found models
    models = []
    if ollama_data and "models" in ollama_data:
        models = ollama_data.get("models", [])
        
    for model in models:
        model_name = model.get("name")
        if not model_name: continue
        
        # Clean tag if needed (e.g. 'latest')
        # We use the full name 'llama3:latest' as model_name for clarity
        
        existing_model = frappe.db.get_value("OwlAI Model", {"model_name": model_name, "provider": provider_doc_name}, "name")
        if not existing_model:
            m = frappe.get_doc({
                "doctype": "OwlAI Model",
                "model_name": model_name,
                "provider": provider_doc_name,
                "context_window": 128000, # Default assumption
                "supports_vision": 0,
                "supports_function_calling": 1
            })
            m.insert(ignore_permissions=True)
            print(f"Registered generic Ollama model: {model_name}")

    if not models:
        # Fallback if list failed but service is up
        print("Warning: No models found via API, adding fallback.")
        models = [{"name": "llama3.2:3b"}]
        # ... (Create fallback if needed)

    return provider_doc_name

def setup_openai():
    # Provider: OpenAI
    existing_provider = frappe.db.get_value("OwlAI Provider", {"provider_name": "OpenAI"}, "name")
    
    if existing_provider:
        provider_doc_name = existing_provider
    else:
        p = frappe.get_doc({
            "doctype": "OwlAI Provider",
            "provider_name": "OpenAI",
            "api_base": "https://api.openai.com/v1",
            "is_default": 1
        })
        p.insert(ignore_permissions=True)
        provider_doc_name = p.name
    
    # Model: GPT-4o-mini
    existing_model = frappe.db.get_value("OwlAI Model", {"model_name": "gpt-4o-mini", "provider": provider_doc_name}, "name")

    if not existing_model:
        m = frappe.get_doc({
            "doctype": "OwlAI Model",
            "model_name": "gpt-4o-mini",
            "provider": provider_doc_name,
            "context_window": 128000,
            "supports_vision": 1,
            "supports_function_calling": 1
        })
        m.insert(ignore_permissions=True)
        
    return provider_doc_name

def setup_default_agent(provider_doc_name):
    # 3. Create Default Agent
    if frappe.db.exists("OwlAI Agent", {"agent_name": "OwlAI Assistant"}):
        agent_doc_name = frappe.db.get_value("OwlAI Agent", {"agent_name": "OwlAI Assistant"}, "name")
        # Force Clean System Prompt if it looks like HTML or is empty
        doc = frappe.get_doc("OwlAI Agent", agent_doc_name)
        clean_prompt = "You are OwlAI, the Native Intelligence Layer for Frappe/ERPNext."
        if "<div" in doc.system_prompt or not doc.system_prompt:
            doc.system_prompt = clean_prompt
            doc.save(ignore_permissions=True)
            print("Fixed OwlAI Assistant System Prompt")
    else:
        # Determine model to link
        # Try to find a model linked to this provider
        model_name = frappe.db.get_value("OwlAI Model", {"provider": provider_doc_name}, "name")
        
        # Get all enabled tools to link to agent
        all_tools = frappe.get_all("OwlAI Tool", fields=["name"])
        agent_tools = []
        for t in all_tools:
            agent_tools.append({
                "tool": t.name,
                "enabled": 1
            })
            
        agent = frappe.get_doc({
            "doctype": "OwlAI Agent",
            "agent_name": "OwlAI Assistant",
            "system_prompt": "You are OwlAI, the Native Intelligence Layer for Frappe/ERPNext.",
            "model": model_name,
            "tools": agent_tools
        })
        agent.insert(ignore_permissions=True)
        agent_doc_name = agent.name

    # 4. Update Settings
    settings = frappe.get_single("OwlAI Settings")
    if not settings.default_agent:
        settings.default_agent = agent_doc_name
        settings.save(ignore_permissions=True)
