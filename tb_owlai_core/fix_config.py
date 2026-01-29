import frappe

def execute():
    # 1. Update OwlAI Assistant Model
    try:
        agent = frappe.get_doc("OwlAI Agent", "OwlAI Assistant")
        # Switch to a tool-capable model. 
        # From debug output: llama3.2:3b-Ollama exists and is used by others.
        agent.model = "llama3.2:3b-Ollama" 
        agent.save()
        frappe.db.commit()
        print(f"Updated OwlAI Assistant to use {agent.model}")
    except frappe.DoesNotExistError:
        print("OwlAI Assistant not found")

    # 2. Update Settings Default Model (Migration)
    settings = frappe.get_single("OwlAI Settings")
    settings.default_model = "llama3.2:3b-Ollama"
    # Ensure embedding model is set
    if not settings.embedding_model:
        settings.embedding_model = "nomic-embed-text"
    settings.save()
    frappe.db.commit()
    print("Updated OwlAI Settings defaults")
