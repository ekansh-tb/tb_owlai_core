import frappe
import requests
from frappe.utils import get_site_name

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
            return {
                "provider": "ollama",
                "model": f"ollama/{settings.ollama_model}",
                "api_base": settings.ollama_url,
                "api_key": "ollama" # Dummy key
            }
        else:
            # Fallback or Error?
            # For "Plug & Play", maybe fallback to Gemini if key exists?
            if settings.gemini_api_key:
                frappe.log_error("Ollama not reachable, falling back to Gemini")
                return {
                    "provider": "gemini",
                    "model": f"gemini/{settings.gemini_model}",
                    "api_key": settings.gemini_api_key
                }
    
    # Default to Gemini
    try:
        api_key = settings.get_password("gemini_api_key")
    except Exception:
        api_key = None

    return {
        "provider": "gemini",
        "model": f"gemini/{settings.gemini_model or 'gemini-1.5-flash'}",
        "api_key": api_key or frappe.conf.get("GEMINI_API_KEY")
    }
