import frappe
import os
import requests

from tb_owlai_core.tool_registry import ToolRegistry


def discover_and_register_providers():
    """
    Scans environment for known API keys and Ollama, registers providers/models.
    Also syncs tools and ensures a default agent exists.
    Zero hardcoded model names — discovers from Ollama API or uses provider defaults.
    """

    # 0. Sync Tools from Plugins
    try:
        ToolRegistry()._sync_tools()
    except Exception as e:
        frappe.log_error(f"Tool Sync during Discovery failed: {e}")

    default_model_link = None

    # 1. Ollama (Local — zero-config primary)
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        resp = requests.get(f"{ollama_host}/api/tags", timeout=3)
        if resp.ok:
            _ensure_provider("Ollama", api_base=ollama_host)
            models = resp.json().get("models", [])
            for m in models:
                model_name = m.get("name", "")
                if model_name:
                    link = _ensure_model(model_name, "Ollama")
                    if not default_model_link:
                        default_model_link = link
    except Exception:
        pass

    # 2. Cloud providers (optional fallbacks via env vars)
    env_providers = [
        ("GROQ_API_KEY", "Groq", None),
        ("ANTHROPIC_API_KEY", "Anthropic", None),
        ("OPENAI_API_KEY", "OpenAI", None),
        ("OPEN_ROUTER_API_KEY", "OpenRouter", "https://openrouter.ai/api/v1"),
    ]

    for env_key, provider_name, api_base in env_providers:
        api_key = os.getenv(env_key)
        if api_key:
            _ensure_provider(provider_name, api_key=api_key, api_base=api_base)

    # 3. Create Default Agent
    _ensure_default_agent(default_model_link)

    # 4. Seed Knowledge Base with Business context (optional)
    try:
        from tb_owlai_core.agno_integrations.auto_seed import seed_knowledge_base
        seed_knowledge_base()
    except ImportError:
        frappe.logger("owlai").info("KB seeding skipped: optional dependencies not installed")
    except Exception as e:
        frappe.log_error(f"KB Auto-Seeding during Discovery failed: {e}")


def _ensure_provider(provider_name, api_key=None, api_base=None):
    """Create provider if it doesn't exist."""
    if frappe.db.exists("OwlAI Provider", provider_name):
        return

    try:
        p = frappe.new_doc("OwlAI Provider")
        p.provider_name = provider_name
        p.api_base = api_base
        p.insert(ignore_permissions=True)
        # Store API key securely via Password field after insert
        if api_key:
            p.set_password("api_key", api_key)
            p.save(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        pass
    except Exception as e:
        frappe.log_error(title=f"Discovery Error: {provider_name}", message=str(e))


def _ensure_model(model_name, provider_name):
    """Create model if it doesn't exist. Returns the model link name."""
    existing = frappe.db.get_value(
        "OwlAI Model", {"model_name": model_name, "provider": provider_name}, "name"
    )
    if existing:
        return existing

    try:
        m = frappe.new_doc("OwlAI Model")
        m.model_name = model_name
        m.provider = provider_name
        m.insert(ignore_permissions=True)
        return m.name
    except frappe.DuplicateEntryError:
        return frappe.db.get_value(
            "OwlAI Model", {"model_name": model_name, "provider": provider_name}, "name"
        )
    except Exception as e:
        frappe.log_error(title=f"Model Discovery Error: {model_name}", message=str(e))
        return None


def _ensure_default_agent(default_model_link=None):
    """Creates default 'Owl Assistant' agent if it doesn't exist."""
    agent_name = "Owl Assistant"

    if frappe.db.exists("OwlAI Agent", agent_name):
        return

    if not default_model_link:
        default_model_link = frappe.db.get_value("OwlAI Model", {}, "name")
        if not default_model_link:
            return

    try:
        agent = frappe.new_doc("OwlAI Agent")
        agent.agent_name = agent_name
        agent.model = default_model_link
        agent.system_prompt = (
            "You are OwlAI, an intelligent assistant for this Frappe system. "
            "You help users navigate, create, read, update, and manage documents. "
            "You operate within the user's permissions — never escalate privileges. "
            "Always be helpful, concise, and action-oriented."
        )

        # Add available tools
        for tool_name in ["get_doctype_info", "list_documents", "get_document",
                          "create_document", "update_document", "delete_document",
                          "search_documents", "navigate", "frappe_utils"]:
            if frappe.db.exists("OwlAI Tool", {"tool_name": tool_name}):
                agent.append("tools", {"tool": tool_name, "enabled": 1})

        agent.insert(ignore_permissions=True)
        frappe.logger("owlai").info(f"Created Agent: {agent_name}")
    except Exception as e:
        frappe.log_error(f"Failed to create Agent {agent_name}: {e}")

    # Set as default in Settings
    try:
        settings = frappe.get_single("OwlAI Settings")
        if not settings.default_agent:
            settings.default_agent = agent_name
            if default_model_link:
                settings.default_model = default_model_link
            settings.save(ignore_permissions=True)
    except Exception:
        pass
