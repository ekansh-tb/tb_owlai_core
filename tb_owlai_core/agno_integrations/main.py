
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
    Factory to create an Agno Agent instance configured with Frappe context.
    
    Args:
        conversation_id (str): The OwlAI Conversation ID (Storage Session ID).
        distinct_id (str): The OwlAI Agent ID/Name to load configuration from.
        model_id (str): Optional override for the model.
        
    Returns:
        Agent: Configured Agno Agent.
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
        "You are an intelligent assistant for Frappe/ERPNext.",
        "When the user asks to 'Open', 'Show', 'Go to' or 'Take me to' a list or a specific document, YOU MUST use the `navigate` tool.",
        "Do NOT just list the items using `list_documents` unless specifically asked to 'List' or 'Find' them without implying navigation.",
        "If the user asks for a 'Pending' list, pass {'status': 'Pending'} (or appropriate filter) to the `navigate` tool's `filters` argument.",
        "Example: 'Show me pending Sales Orders' -> navigate(doctype='Sales Order', filters={'status': 'Pending'})",
        "Example: 'Open Todo list' -> navigate(doctype='Todo')",
        "If the user request is ambiguous (e.g. 'Show orders' without specifying Sales or Purchase), ASK A CLARIFYING QUESTION.",
        "Use `search_knowledge_base` if the user asks about policies, manuals, or general company information that might be stored in files.",
    ]
    
    # Inject Dynamic Context
    try:
        if conversation_id:
             # Try to get route from conversation doc if available, or pass it in? 
             # Ideally get_agent should accept 'route' argument if possible, or we rely on stored context.
             # For now, let's inject System/Company/User context which is stable.
             pass
             
        instructions.append(context_builder.get_system_context())
        instructions.append(context_builder.get_company_context())
        instructions.append(context_builder.get_user_context())
        instructions.append(context_builder.get_common_doctypes())
    except Exception as e:
        frappe.log_error(f"Context Build Error: {e}")

    if agent_doc and agent_doc.system_prompt:
        instructions.append(agent_doc.system_prompt)
        
    # 5. Tools
    # For "Generic Product", we just inject the FrappeToolkit which exposes everything allowed by Registry.
    # Future: Filter tools based on agent_doc.tools list
    selected_tools = None
    if agent_doc:
        selected_tools = []
        if agent_doc.tools:
            for t in agent_doc.tools:
                if t.enabled:
                    # 'tool' field is the Link to OwlAI Tool -> name matches tool_name
                    selected_tools.append(t.tool)
    
    tools_list = [FrappeToolkit(selected_tools=selected_tools)]

    # 6. Instantiate Agent
    agent = Agent(
        model=model_instance,
        tools=tools_list,
        db=FrappeStorage(),
        session_id=conversation_id,
        instructions=instructions,
        description=f"Agent: {agent_name}",
        add_history_to_context=True, 
        num_history_runs=5, # Keep context small for now
        debug_mode=debug_mode,
        markdown=True
    )
    
    return agent
