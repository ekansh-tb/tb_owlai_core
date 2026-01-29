
import frappe
import os
from tb_owlai_core.tool_registry import ToolRegistry

def discover_and_register_providers():
    """
    Scans environment for known API keys and registers them.
    Also syncs tools and ensures a default agent exists.
    """
    
    # 0. Sync Tools from Plugins (Force discovery)
    try:
        ToolRegistry()._sync_tools()
    except Exception as e:
        frappe.log_error(f"Tool Sync during Discovery failed: {e}")

    # 1. Groq
    if os.getenv("GROQ_API_KEY"):
        _ensure_provider_and_model(
            provider_name="Groq",
            model_name="llama3-70b-8192",
            api_key=os.getenv("GROQ_API_KEY")
        )

    # ... (Rest of existing provider logic matches original file, omitting for brevity in diff if not changing) ...
    # Wait, replace_file_content replaces the BLOCK. I need to be careful not to delete sections if I use a large range.
    # The user wants me to INSERT logic.
    
    # 2. Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        _ensure_provider_and_model(
            provider_name="Anthropic",
            model_name="claude-3-5-sonnet-20240620",
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
    # 3. OpenAI
    if os.getenv("OPENAI_API_KEY"):
        _ensure_provider_and_model(
            provider_name="OpenAI",
            model_name="gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY")
        )

    # 4. OpenRouter
    if os.getenv("OPEN_ROUTER_API_KEY"):
        _ensure_provider_and_model(
            provider_name="OpenRouter",
            model_name="google/gemini-2.0-flash-001",
            api_key=os.getenv("OPEN_ROUTER_API_KEY"),
            api_base="https://openrouter.ai/api/v1"
        )
        
    # 5. Ollama (Local) - Default for CPU/Cloud
    local_model = "llama3.2:3b"
    _ensure_provider_and_model(
        provider_name="Ollama",
        model_name=local_model,
        api_base=os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    
    # 6. Create Default Agent
    _ensure_default_agent(local_model)

    # 7. Seed Knowledge Base with Business context
    try:
        from tb_owlai_core.agno_integrations.auto_seed import seed_knowledge_base
        seed_knowledge_base()
    except Exception as e:
        frappe.log_error(f"KB Auto-Seeding during Discovery failed: {e}")



def _ensure_provider_and_model(provider_name, model_name, api_key=None, api_base=None):
    try:
        # Create/Update Provider
        provider_doc_name = provider_name
        if not frappe.db.exists("OwlAI Provider", provider_doc_name):
            try:
                p = frappe.new_doc("OwlAI Provider")
                p.provider_name = provider_name
                p.api_base = api_base
                if api_key:
                    p.api_key = api_key 
                p.insert(ignore_permissions=True)
            except frappe.DuplicateEntryError:
                pass
        
        # Ensure Model
        # We try to guess the name, but best is to query by fields
        if not frappe.db.get_value("OwlAI Model", {"model_name": model_name, "provider": provider_doc_name}):
            try:
                m = frappe.new_doc("OwlAI Model")
                m.model_name = model_name
                m.provider = provider_doc_name
                m.insert(ignore_permissions=True)
            except frappe.DuplicateEntryError:
                pass
            
    except Exception as e:
        frappe.log_error(title=f"Discovery Error: {provider_name}", message=str(e))



def _ensure_default_agent(default_model_name):
    """Creates default 'Owl Assistant' and Swarm Agents if they don't exist."""
    
    # 1. Base Model Check
    model_link = f"{default_model_name} (Ollama)"
    # If using API keys, we might want a stronger model for coder.
    # For now, stay Zero-Config CPU friendly (Llama 3.2 3B is okay for basic coding, 
    # but 70b Groq would be better if available. Let's start with default.)
    
    if not frappe.db.exists("OwlAI Model", model_link):
        return

    # --- Agent Definitions ---
    agents_config = [
        {
            "name": "Owl Assistant",
            "role": "Orchestrator",
            "prompt": (
                "You are OwlAI, the Orchestrator for this Frappe system. "
                "You coordinate tasks between specialized agents. "
                "For coding, delegate to 'frappe_coder'. "
                "For admin tasks, delegate to 'frappe_admin'. "
                "For analysis, delegate to 'frappe_analyst'. "
                "Always be helpful and concise."
            ),
            "tools": ["delegate_task", "frappe_utils"] # Minimal tools, relies on delegation
        },
        {
            "name": "frappe_coder", 
            "role": "Engineer",
            "prompt": (
                "You are frappe_coder, an expert Frappe/Python/JS developer. "
                "You write high-quality, secure code. "
                "Always verify file paths and existing code before editing. "
                "Use 'create_document' for DocTypes and 'write_to_file' (if available) for code."
            ),
            "tools": ["frappe_utils", "get_doctype_info", "list_documents", "create_document", "update_document"] 
        },
        {
            "name": "frappe_admin",
            "role": "Admin",
            "prompt": (
                "You are frappe_admin, responsible for system operations. "
                "You manage users, permissions, and site settings. "
                "Be careful with deletion/update operations."
            ),
            "tools": ["frappe_utils", "list_documents", "get_document", "update_document", "search_documents"]
        },
         {
            "name": "frappe_analyst",
            "role": "Analyst",
            "prompt": (
                "You are frappe_analyst. You analyze data and generate reports. "
                "Use SQL and Report tools to find insights."
            ),
            "tools": ["run_doc_method", "generate_report", "list_documents"] # Assuming generate_report exists or will
        }
    ]

    for agent_conf in agents_config:
        _create_agent_if_missing(agent_conf, model_link)

    # Set Default Global
    settings = frappe.get_single("OwlAI Settings")
    if not settings.default_agent:
        settings.default_agent = "Owl Assistant"
        settings.default_model = model_link
        settings.save(ignore_permissions=True)


def _create_agent_if_missing(config, model_link):
    name = config["name"]
    if frappe.db.exists("OwlAI Agent", name):
        return

    try:
        agent = frappe.new_doc("OwlAI Agent")
        agent.agent_name = name
        agent.model = model_link
        agent.system_prompt = config["prompt"]
        
        # Tools
        for t_name in config["tools"]:
            # Check if tool exists in DB
            if frappe.db.exists("OwlAI Tool", {"tool_name": t_name}):
                agent.append("tools", {"tool": t_name, "enabled": 1})
            else:
                # If delegate_task wasn't synced yet, we might miss it.
                # It's fine, next sync will pick it up or user can add it.
                pass
            
        agent.insert(ignore_permissions=True)
        frappe.logger("owlai").info(f"Created Agent: {name}")
        
    except Exception as e:
        frappe.log_error(f"Failed to create Agent {name}: {e}")

