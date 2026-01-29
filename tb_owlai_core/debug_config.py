import frappe

def execute():
    print("--- Agents ---")
    agents = frappe.get_all("OwlAI Agent", fields=["name", "model"])
    for a in agents:
        print(f"Agent: {a.name}, Model: {a.model}")
        
    print("\n--- Models ---")
    models = frappe.get_all("OwlAI Model", fields=["name", "provider", "model_name"])
    for m in models:
        print(f"Model: {m.name}, Provider: {m.provider}, Ref Name: {m.model_name}")
        
    print("\n--- Providers ---")
    providers = frappe.get_all("OwlAI Provider", fields=["name", "provider_name", "api_base"])
    for p in providers:
        print(f"Provider: {p.name}, Type: {p.provider_name}, Base: {p.api_base}")
        
    print("\n--- Settings ---")
    settings = frappe.get_single("OwlAI Settings")
    print(f"Provider: {settings.provider}")
    print(f"Ollama Model: {settings.ollama_model}")
    print(f"Ollama URL: {settings.ollama_url}")
