
import frappe
from crewai import Crew, Process
from tb_owlai_core.crewai_integrations.agent_adapter import AgentAdapter
from tb_owlai_core.crewai_integrations.task_adapter import TaskAdapter

class CrewManager:
    def __init__(self):
        self.agent_adapter = AgentAdapter()
        self.task_adapter = TaskAdapter()

    def run_crew(self, crew_name, inputs=None):
        """
        Runs a Crew based on the OwlAI Crew DocType.
        """
        if not frappe.db.exists("OwlAI Crew", crew_name):
            frappe.throw(f"OwlAI Crew '{crew_name}' not found.")
            
        crew_doc = frappe.get_doc("OwlAI Crew", crew_name)
        
        # Gather Agents
        # Note: CrewAI Agents are often inferred from Tasks, but explicit list is good too.
        # We need to instantiate them ensuring shared tools/memory if needed.
        agents = []
        for agent_entry in crew_doc.agents:
            agents.append(self.agent_adapter.get_agent(agent_entry.agent))
            
        # Gather Tasks
        tasks = []
        for task_entry in crew_doc.tasks:
            tasks.append(self.task_adapter.get_task(task_entry.task))

        # Process Mapping
        process_map = {
            "Sequential": Process.sequential,
            "Hierarchical": Process.hierarchical
        }
        process = process_map.get(crew_doc.execution_process, Process.sequential)

        # Initialize Crew
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=process,
            verbose=bool(crew_doc.verbose),
            # manager_llm=... # Needed for Hierarchical
        )

        # Kickoff
        result = crew.kickoff(inputs=inputs)
        return result
