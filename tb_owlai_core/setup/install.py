import frappe
import shutil
from frappe.utils import cint

def after_install():
    """
    Called after the app is installed.
    Checks if Ollama is available globally and auto-configures OwlAI Settings.
    """
    try:
        settings = frappe.get_single("OwlAI Settings")
        
        # Check for 'ollama' binary in path
        if shutil.which("ollama"):
            frappe.msgprint("🦉 OwlAI Setup: ✅ Ollama detected on server. Local AI is ready!")
            
            # Automatically enable Local LLM in settings
            settings.enable_local_llm = 1
            settings.provider = "Local (Ollama)"
            settings.save()
            frappe.db.commit()
        else:
            frappe.msgprint("🦉 OwlAI Setup: ⚠️ Ollama not found. Defaulting to Cloud (Gemini).")
            frappe.msgprint("Tip: Install Ollama ('curl -fsSL https://ollama.com/install.sh | sh') for Local AI.")
            
    except Exception as e:
        print(f"OwlAI Setup Error: {e}")
