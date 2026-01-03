import frappe
import sys
import os

# Setup Path to include apps
current_dir = os.path.dirname(os.path.abspath(__file__)) # apps/tb_owlai_core/tb_owlai_core
app_root = os.path.dirname(current_dir) # apps/tb_owlai_core
apps_dir = os.path.dirname(app_root) # apps
bench_dir = os.path.dirname(apps_dir) # frappe-bench

if app_root not in sys.path:
    sys.path.insert(0, app_root)
if apps_dir not in sys.path:
    sys.path.insert(0, apps_dir)

def test_local_llm():
    """
    Test script for OwlAI Local LLM Integration.
    """
    print("🔍 [1/3] Checking Ollama Status...")
    # Correct import based on package structure
    try:
        from tb_owlai_core.utils import check_ollama_status
    except ImportError:
         print("❌ Import Error: Could not import tb_owlai_core.utils. Check python path.")
         return

    is_running = check_ollama_status()
    if not is_running:
        print("❌ Ollama is NOT running on http://localhost:11434")
        print("   Please start Ollama first (e.g. 'ollama serve')")
        return

    print("✅ Ollama is running!")
    
    print("\n⚙️ [2/3] Configuring OwlAI Settings...")
    settings = frappe.get_single("OwlAI Settings")
    original_provider = settings.provider
    
    # Force use Local
    settings.enabled = 1
    settings.provider = "Local (Ollama)"
    
    # Check if model is set
    if not settings.ollama_model:
        settings.ollama_model = "llama3"
        print(f"   Setting default model to {settings.ollama_model}")
        
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"   Provider set to: {settings.provider}")
    print(f"   Model set to: {settings.ollama_model}")

    print("\n💬 [3/3] Sending Test Message...")
    from tb_owlai_core.api.router import handle_input_v2
    
    try:
        # Mocking a simple "Hello" request
        response = handle_input_v2(text="Hello! Are you running locally via Ollama?", conversation_id=None)
        
        reply = response.get("reply")
        print("\n✅ Response Received:")
        print("-" * 40)
        print(reply)
        print("-" * 40)
        
        if response.get("conversation_id"):
            print(f"   Conversation ID: {response.get('conversation_id')}")

    except Exception as e:
        print(f"\n❌ Error during execution: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        pass

def run():
    # If run via bench execute, frappe is already connected
    test_local_llm()

if __name__ == "__main__":
    # If run as standalone script
    try:
        frappe.init(site="waha.local")
        frappe.connect()
        test_local_llm()
    except Exception as e:
        print(f"Failed to connect to Frappe: {e}")
