
import frappe
from agno.models.ollama import Ollama
import os

# Provider Classes (Lazy Import where possible or standard Agno imports)
try:
    from agno.models.openai import OpenAIChat
except ImportError:
    OpenAIChat = None

try:
    from agno.models.groq import Groq
except ImportError:
    Groq = None

try:
    from agno.models.anthropic import Claude
except ImportError:
    Claude = None
    
def get_best_available_model():
    """
    Zero-Config Logic: Scans environment for API keys and returns the best available model.
    Priority:
    1. Groq (Fast & Cheap) - Llama3-70b
    2. Anthropic (High Quality) - Sonnet 3.5
    3. OpenRouter (Flexible) - Auto
    4. OpenAI (Standard) - GPT-4o
    5. Ollama (Local Fallback)
    """
    if os.getenv("GROQ_API_KEY") and Groq:
        return Groq(id="llama3-70b-8192", api_key=os.getenv("GROQ_API_KEY"))
    
    if os.getenv("ANTHROPIC_API_KEY") and Claude:
        return Claude(id="claude-3-5-sonnet-20240620", api_key=os.getenv("ANTHROPIC_API_KEY"))

    if os.getenv("OPEN_ROUTER_API_KEY") and OpenAIChat:
        # OpenRouter uses OpenAI Client base
        return OpenAIChat(
            id="gpt-4o", # Default or specific router model
            api_key=os.getenv("OPEN_ROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
        
    if os.getenv("OPENAI_API_KEY") and OpenAIChat:
        return OpenAIChat(id="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
        
    # Fallback to Ollama
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return Ollama(id="llama3.2:3b", host=host)

def get_model_instance(model_link_name):
    """
    Factory to return a configured Agno Model instance.
    """
    # 1. Zero Config / Default
    if not model_link_name:
        # Check settings first
        settings = frappe.get_single("OwlAI Settings")
        if settings.default_model:
             # If user explicitly set a default in DB, use it
             model_link_name = settings.default_model
        else:
             # Fully automated discovery
             return get_best_available_model()

    if not frappe.db.exists("OwlAI Model", model_link_name):
        frappe.log_error(f"Model not found: {model_link_name}")
        return get_best_available_model()

    model_doc = frappe.get_doc("OwlAI Model", model_link_name)
    provider_doc = frappe.get_doc("OwlAI Provider", model_doc.provider)
    
    provider_type = provider_doc.provider_name
    model_id = model_doc.model_name
    api_key = provider_doc.get_password("api_key", raise_exception=False)
    api_base = provider_doc.api_base
    
    # --- Provider Logic ---
    
    if provider_type == "Ollama":
        return Ollama(id=model_id, host=api_base if api_base else None)

    elif provider_type == "Groq":
        if not Groq: frappe.throw("Agno Groq module (pip install agno[groq]) not found.")
        return Groq(id=model_id, api_key=api_key)
        
    elif provider_type == "Anthropic":
        if not Claude: frappe.throw("Agno Anthropic module not found.")
        return Claude(id=model_id, api_key=api_key)

    elif provider_type == "OpenAI":
        if not OpenAIChat: frappe.throw("Agno OpenAI module not found.")
        return OpenAIChat(id=model_id, api_key=api_key, base_url=api_base or None)
        
    elif provider_type == "OpenRouter":
        if not OpenAIChat: frappe.throw("Agno OpenAI module needed for OpenRouter.")
        return OpenAIChat(
            id=model_id,
            api_key=api_key,
            base_url=api_base or "https://openrouter.ai/api/v1"
        )

    # Fallback
    frappe.msgprint(f"Provider {provider_type} not natively supported. Using Ollama fallback.")
    return Ollama(id=model_id)
