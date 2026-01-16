
import frappe
from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat
# from agno.models.google import Gemini # Requires agno[google]
# from agno.models.anthropic import Claude # Requires agno[anthropic]

def get_model_instance(model_link_name):
    """
    Factory to return a configured Agno Model instance based on OwlAI Model configuration.
    
    Args:
        model_link_name (str): The name/ID of the OwlAI Model document (e.g. 'gpt-4o-OpenAI')
        
    Returns:
        agno.models.base.Model: Configured model instance.
    """
    if not model_link_name or not frappe.db.exists("OwlAI Model", model_link_name):
        frappe.log_error(f"Model not found: {model_link_name}")
        # Fallback to default Ollama if possible, or raise
        settings = frappe.get_single("OwlAI Settings")
        return Ollama(id=settings.ollama_model or "llama3")

    model_doc = frappe.get_doc("OwlAI Model", model_link_name)
    provider_doc = frappe.get_doc("OwlAI Provider", model_doc.provider)
    
    provider_type = provider_doc.provider_name # Select field: OpenAI, Ollama, etc.
    model_id = model_doc.model_name
    
    # 1. Ollama
    if provider_type == "Ollama":
        base_url = provider_doc.api_base
        return Ollama(
            id=model_id,
            host=base_url if base_url else None
        )

    # 2. OpenAI
    elif provider_type == "OpenAI":
        api_key = provider_doc.get_password("api_key")
        base_url = provider_doc.api_base # Optional for proxies
        return OpenAIChat(
            id=model_id,
            api_key=api_key,
            base_url=base_url if base_url else None
        )
        
    # 3. Google Gemini
    elif provider_type == "Google Gemini":
        try:
            from agno.models.google import Gemini
            api_key = provider_doc.get_password("api_key")
            return Gemini(
                id=model_id,
                api_key=api_key
            )
        except ImportError:
            frappe.throw("Agno Google module not installed. Run 'pip install agno[google]'")

    # 4. Anthropic
    elif provider_type == "Anthropic":
        try:
            from agno.models.anthropic import Claude
            api_key = provider_doc.get_password("api_key")
            return Claude(
                id=model_id,
                api_key=api_key
            )
        except ImportError:
            frappe.throw("Agno Anthropic module not installed. Run 'pip install agno[anthropic]'")

    # Fallback / Unknown
    frappe.msgprint(f"Warning: Provider {provider_type} not fully supported, defaulting to Ollama emulation.")
    return Ollama(id=model_id)
