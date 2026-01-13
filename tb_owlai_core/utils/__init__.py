import frappe
import requests
from frappe.utils import get_site_name, format_date, now_datetime, money_in_words, validate_email_address

def check_ollama_status(url="http://localhost:11434"):
    """
    Pings the Ollama server to see if it's running.
    Returns True if accessible, False otherwise.
    """
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return True
    except Exception:
        pass
    return False

def _get_model_name(model_link):
    """Helper to resolve model name from a Link or raw string."""
    if not model_link:
        return ""
    if frappe.db.exists("OwlAI Model", model_link):
        return frappe.db.get_value("OwlAI Model", model_link, "model_name")
    return model_link

def get_active_provider_config():
    """
    Returns the configuration for the active LLM provider.
    Prioritizes 'Local (Ollama)' if enabled and available in settings.
    Falls back to Gemini.
    """
    settings = frappe.get_single("OwlAI Settings")
    
    if not settings.enabled:
        return None

    # Check Local first if selected
    if settings.provider == "Local (Ollama)":
        if check_ollama_status(settings.ollama_url):
            model_name = _get_model_name(settings.ollama_model)
            return {
                "provider": "ollama",
                "model": f"ollama/{model_name}",
                "model_doc_name": settings.ollama_model, 
                "api_base": settings.ollama_url,
                "api_key": "ollama" # Dummy key
            }
        else:
            # Fallback or Error?
            # For "Plug & Play", maybe fallback to Gemini if key exists?
            if settings.gemini_api_key:
                frappe.log_error("Ollama not reachable, falling back to Gemini")
                model_name = _get_model_name(settings.gemini_model)
                return {
                    "provider": "gemini",
                    "model": f"gemini/{model_name}",
                    "model_doc_name": settings.gemini_model,
                    "api_key": settings.gemini_api_key
                }
    
    # Default to Gemini
    try:
        api_key = settings.get_password("gemini_api_key")
    except Exception:
        api_key = None
    
    model_name = _get_model_name(settings.gemini_model) or "gemini-1.5-flash"

    return {
        "provider": "gemini",
        "model": f"gemini/{model_name}",
        "model_doc_name": settings.gemini_model,
        "api_key": api_key or frappe.conf.get("GEMINI_API_KEY")
    }
