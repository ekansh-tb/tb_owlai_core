
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
        "You are an intelligent assistant for Frappe/ERPNext.",
        "1. Navigation: Use `navigate` tool for requests like 'Open', 'Show', 'Go to'. Example: 'Show pending Sales Orders' -> navigate(doctype='Sales Order', filters={'status': 'Pending'}).",
        "2. Listing: Use `list_documents` only when explicitly asked to 'List' or 'Find' items.",
        "3. Clarification: If ambiguous (e.g. 'Show orders'), ask for clarification.",
        "4. Knowledge Base: Use `search_knowledge_base` ONLY for internal policies, manuals, or company docs.",
        "5. External Search: Use `duckduckgo_search` (if available) for real-time info (prices, news, weather) or general knowledge.",
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
    tools_list = []
    
    # Identify enabled tools
    frappe_tools = []
    native_tools = []
    
    if agent_doc and agent_doc.tools:
        for t in agent_doc.tools:
            if t.enabled:
                tool_name = t.tool # Name of the OwlAI Tool document
                
                # Check for Native Agno Tools
                if tool_name == "Web Search" or tool_name == "DuckDuckGo":
                    try:
                        from agno.tools.duckduckgo import DuckDuckGoTools
                        native_tools.append(DuckDuckGoTools(fixed_max_results=5))
                    except ImportError:
                        frappe.log_error("DuckDuckGo Tool Import Error", "OwlAI")
                
                elif tool_name == "Exa Search":
                    try:
                        from agno.tools.exa import ExaTools
                        # api_key should be in environment or passed
                        # Assuming env var EXA_API_KEY is set or we fetch from settings
                        native_tools.append(ExaTools())
                    except:
                         pass
                         
                else:
                    # Assume it's a Frappe Toolkit tool
                    frappe_tools.append(tool_name)
    
    # Always include FrappeToolkit (generic) if no specific tools selected, 
    # OR if specific frappe tools are selected.
    # If agent has NO tools defined, we give it everything by default (legacy behavior)
    if not agent_doc or not agent_doc.tools:
         tools_list.append(FrappeToolkit())
    elif frappe_tools:
         tools_list.append(FrappeToolkit(selected_tools=frappe_tools))

    # Add Native Tools
    tools_list.extend(native_tools)



    # 6. Instantiate Agent
    
    # Context Compression
    from agno.compression.manager import CompressionManager
    compression_manager = CompressionManager(
        model=model_instance,
        compress_tool_results=True,
        compress_token_limit=10000,
    )
    
    extra_instructions = [
        "Use `get_doctype_info(doctype=...)` if you need to know the field names before creating or updating a document.",
        "Always double-check the 'name' (ID) of a document before updating it."
    ]
    instructions.extend(extra_instructions)

    agent = Agent(
        model=model_instance,
        tools=tools_list,
        db=FrappeStorage(), 
        session_id=conversation_id,
        instructions=instructions,
        description=f"Agent: {agent_name}",
        add_history_to_context=True, 
        num_history_runs=5,
        debug_mode=debug_mode,
        markdown=True,
        # Compression & Memory
        compression_manager=compression_manager,
        enable_agentic_memory=True,
        enable_user_memories=True,
        add_memories_to_context=True,
    )

    
    return agent

