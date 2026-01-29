
import frappe
from crewai import Agent
from tb_owlai_core.utils.plugin_manager import PluginManager

class AgentAdapter:
    def __init__(self):
        self.plugin_manager = PluginManager()
        self._cache = {}

    def get_agent(self, agent_name):
        """
        Converts an OwlAI Agent DocType to a crewai.Agent object.
        """
        if agent_name in self._cache:
            return self._cache[agent_name]

        if not frappe.db.exists("OwlAI Agent", agent_name):
            frappe.throw(f"OwlAI Agent '{agent_name}' not found.")

        agent_doc = frappe.get_doc("OwlAI Agent", agent_name)

        # Tools
        tools = self._get_tools(agent_doc.tools)

        # Model used by Agent (Assuming simple string or LLM object handled by CrewAI/LiteLLM)
        # For now, we'll pass the model name string if supported, or let CrewAI handle default.
        # But we should probably look up the OwlAI Model doc to get the actual model name.
        model_name = self._get_model_name(agent_doc.model)
        
        # CrewAI Agent
        return Agent(
            role=agent_doc.agent_role or "Agent",
            goal=agent_doc.goal or "Complete the assigned task.",
            backstory=agent_doc.backstory or "You are a helpful assistant.",
            allow_delegation=bool(agent_doc.allow_delegation),
            verbose=bool(agent_doc.verbose),
            memory=bool(agent_doc.memory),
            tools=tools,
            llm=model_name # CrewAI supports passing model name string (provider/model) often
        )
        
        self._cache[agent_name] = agent
        return agent

    def _get_tools(self, tools_table):
        """
        Resolves tools from the child table to actual callable functions or CrewAI tools.
        """
        resolved_tools = []
        # TODO: Implement Tool Registry Lookup compatible with CrewAI
        # For now, we will return an empty list or implement basic lookup
        
        # from tb_owlai_core.tool_registry import ToolRegistry
        # registry = ToolRegistry()
        # for t in tools_table:
        #     tool_instance = registry.get_crewai_tool(t.tool_name)
        #     if tool_instance:
        #         resolved_tools.append(tool_instance)
        
        return resolved_tools

    def _get_model_name(self, model_link):
        if not model_link:
            return "gpt-4" # Default fallback
        
        # Fetch OwlAI Model doc
        model_doc = frappe.get_doc("OwlAI Model", model_link)
        # Assuming OwlAI Model has a field 'model_id' or similar that maps to litellm/crewai expected string
        # Let's verify OwlAI Model structure later. For now assuming 'name' or 'model_name'
        return model_doc.model_name or model_doc.name
