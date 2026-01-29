
from agno.agent import Agent
from agno.models.ollama import Ollama
# from agno.models.google import Gemini # If we install agno[google]
# For now, standard Ollama support.

import frappe
from tb_owlai_core.agno_integrations.storage import FrappeStorage
from tb_owlai_core.agno_integrations.tools import FrappeToolkit
from tb_owlai_core.agno_integrations.model_factory import get_model_instance

def get_agent(conversation_id=None, distinct_id=None, model_id=None, debug_mode=True):
    """
    Factory to create an OwlAi Agent instance configured with Frappe context.
    
    Args:
        conversation_id (str): The OwlAI Conversation ID (Storage Session ID).
        distinct_id (str): The OwlAI Agent ID/Name to load configuration from.
        model_id (str): Optional override for the model.
        
    Returns:
        Agent: Configured OwlAi Agent.
    """
    
    # 1. Load Settings & Defaults
    settings = frappe.get_single("OwlAI Settings")
    agent_name = distinct_id or settings.default_agent or "OwlAI Assistant"
    
    agent_doc = None
    if frappe.db.exists("OwlAI Agent", {"agent_name": agent_name}):
        name = frappe.db.get_value("OwlAI Agent", {"agent_name": agent_name}, "name")
        agent_doc = frappe.get_doc("OwlAI Agent", name)
        
    # 2. Determine Model Link Name
    # Logic: Agent Model > Settings default
    model_link_name = model_id
    if not model_link_name and agent_doc:
        model_link_name = agent_doc.model
    if not model_link_name:
        model_link_name = settings.ollama_model # Fallback
        
    # 3. Configure LLM Backend via Factory
    model_instance = get_model_instance(model_link_name)
    
    # 4. System Prompt / Instructions
    from tb_owlai_core.agno_integrations import context_builder
    
    # Base Instructions (Role & Capabilities)
    instructions = [
        "You are **OwlAI**, the high-performance intelligence layer for Frappe/ERPNext.",
        "GOAL: Execute user requests with LIGHTNING speed and zero hallucination.",
        
        "### CORE PROTOCOLS:",
        "1. **Direct Action**: If intent is clear (e.g. 'Create item X'), use the tool immediately. Don't ask for permission.",
        "2. **Case-Perfect Linking**: When creating/finding records, provide a link: `[View {DocType} {Name}](/app/{slug}/{name})`.",
        "   - **URGENT**: The `{name}` in the URL MUST match the tool output EXACTLY (case-sensitive). If the ID is 'Suraj', link MUST be `/app/customer/Suraj`.",
        "   - `{slug}` is lowercase: 'Sales Order' -> 'sales-order'.",
        "3. **Minimal Reasoning**: Only use chain-of-thought for complex logic. For simple CRUD, be brief and execute.",
        "4. **Smart Schema**: Use `get_doctype_info` only if you are unsure of mandatory fields. Check cache results first."
    ]
    
    # Inject minimal dynamic business context (Only essential)
    try:
        # 1. Environment & Persona (Cached)
        instructions.append(context_builder.get_system_context()) 
        # 2. Business Context
        instructions.append(context_builder.get_company_context())
        # 3. User Identity
        instructions.append(context_builder.get_user_context())
        
        # 4. Strict Persona Rule
        instructions.append("""
### SYSTEM PERSONA:
- You are a precise execution agent. 
- You REMEMBER that the current site is provided in metadata.
- You NEVER guess or trial-and-error site names.
- You ALWAYS use the exact casing for IDs. 'suraj' != 'Suraj'.
- You are LIGHTNING fast because you skip unnecessary reasoning on repetitive tasks.
""")
    except Exception as e:
        frappe.log_error(f"Context Build Error: {e}")

    if agent_doc and agent_doc.system_prompt:
        instructions.append(agent_doc.system_prompt)
        
    # 5. Tools
    tools_list = []
    
    # Identify enabled tools
    frappe_tools = []
    if agent_doc and agent_doc.tools:
        for t in agent_doc.tools:
            if t.enabled:
                frappe_tools.append(t.tool)
    
    if not agent_doc or not agent_doc.tools:
         tools_list.append(FrappeToolkit())
    else:
         tools_list.append(FrappeToolkit(selected_tools=frappe_tools))

    # 6. Instantiate Agent
    from agno.compression.manager import CompressionManager
    compression_manager = CompressionManager(
        model=model_instance,
        compress_tool_results=True,
        compress_token_limit=5000, # More aggressive compression for speed
    )
    
    agent = Agent(
        model=model_instance,
        tools=tools_list,
        db=FrappeStorage(), 
        session_id=conversation_id,
        instructions=instructions,
        description=f"OwlAI Agent: {agent_name}",
        add_history_to_context=True, 
        num_history_runs=3, # Reduced for faster context processing
        debug_mode=debug_mode,
        markdown=True,
        # Performance Settings
        compression_manager=compression_manager,
        enable_agentic_memory=True,
        enable_user_memories=True,
        add_memories_to_context=True,
    )

    
    return agent

