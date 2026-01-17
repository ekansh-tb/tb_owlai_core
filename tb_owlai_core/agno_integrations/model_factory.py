
import frappe
from agno.models.ollama import Ollama

def get_model_instance(model_link_name):
    """
    Factory to return a configured Agno Model instance based on OwlAI Model configuration.
    Prioritizes Local LLM (Ollama).
    
    Args:
        model_link_name (str): The name/ID of the OwlAI Model document.
        
    Returns:
        agno.models.base.Model: Configured model instance.
    """
    # 1. Default to Settings if no specific model provided
    if not model_link_name:
        settings = frappe.get_single("OwlAI Settings")
        return Ollama(id=settings.ollama_model or "qwen2.5:3b")

    if not frappe.db.exists("OwlAI Model", model_link_name):
        frappe.log_error(f"Model not found: {model_link_name}")
        return Ollama(id="qwen2.5:3b")

    model_doc = frappe.get_doc("OwlAI Model", model_link_name)
    provider_doc = frappe.get_doc("OwlAI Provider", model_doc.provider)
    
    provider_type = provider_doc.provider_name
    model_id = model_doc.model_name
    
    # 2. Ollama (Primary)
    if provider_type == "Ollama":
        base_url = provider_doc.api_base
        return Ollama(
            id=model_id,
            host=base_url if base_url else None
        )

    # 3. External Providers (Optional)
    # Kept minimal to avoid bloat. Uncomment/Extend as needed.
    elif provider_type == "OpenAI":
        try:
            from agno.models.openai import OpenAIChat
            return OpenAIChat(
                id=model_id,
                api_key=provider_doc.get_password("api_key"),
                base_url=provider_doc.api_base or None
            )
        except ImportError:
            frappe.throw("Agno OpenAI module not installed.")

    # Fallback
    frappe.msgprint(f"Provider {provider_type} not supported in Local-First mode. Using Ollama emulation.")
    return Ollama(id=model_id)
