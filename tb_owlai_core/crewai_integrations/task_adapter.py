
import frappe
from crewai import Task
from tb_owlai_core.crewai_integrations.agent_adapter import AgentAdapter

class TaskAdapter:
    def __init__(self):
        self.agent_adapter = AgentAdapter()
        self._cache = {}

    def get_task(self, task_name):
        """
        Converts an OwlAI Task DocType to a crewai.Task object.
        """
        if task_name in self._cache:
             return self._cache[task_name]

        if not frappe.db.exists("OwlAI Task", task_name):
            frappe.throw(f"OwlAI Task '{task_name}' not found.")
            
        task_doc = frappe.get_doc("OwlAI Task", task_name)
        
        agent = None
        if task_doc.agent:
            agent = self.agent_adapter.get_agent(task_doc.agent)

        
        context_tasks = []
        if hasattr(task_doc, "context") and task_doc.context:
            for context_entry in task_doc.context:
                # We need to fetch the actual Task object for context
                # Recursion alert: If we use get_task() here, we might get infinite recursion 
                # if there are circular dependencies. CrewAI handles DAGs, but our adapter 
                # needs to be careful.
                # For now, we assume users define DAGs correctly.
                # However, get_task instantiates a NEW Task object every time. 
                # CrewAI might rely on object identity. 
                # Ideally, we should have a Task Registry or Cache in the Manager level.
                # But to keep it simple: we just create the task.
                context_tasks.append(self.get_task(context_entry.task))

        return Task(
            description=task_doc.description,
            expected_output=task_doc.expected_output,
            agent=agent,
            async_execution=bool(task_doc.async_execution),
            context=context_tasks
        )
        
        self._cache[task_name] = task
        return task
