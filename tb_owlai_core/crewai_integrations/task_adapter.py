
import frappe
from crewai import Task
from tb_owlai_core.crewai_integrations.agent_adapter import AgentAdapter

class TaskAdapter:
    def __init__(self):
        self.agent_adapter = AgentAdapter()

    def get_task(self, task_name):
        """
        Converts an OwlAI Task DocType to a crewai.Task object.
        """
        if not frappe.db.exists("OwlAI Task", task_name):
            frappe.throw(f"OwlAI Task '{task_name}' not found.")
            
        task_doc = frappe.get_doc("OwlAI Task", task_name)
        
        agent = None
        if task_doc.agent:
            agent = self.agent_adapter.get_agent(task_doc.agent)

        return Task(
            description=task_doc.description,
            expected_output=task_doc.expected_output,
            agent=agent,
            async_execution=bool(task_doc.async_execution)
        )
