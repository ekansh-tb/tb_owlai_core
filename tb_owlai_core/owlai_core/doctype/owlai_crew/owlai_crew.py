# Copyright (c) 2024, TechBirdIt.in and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from crewai import Agent, Task, Crew, Process
from tb_owlai_core.utils.llm_factory import get_llm
from tb_owlai_core.tool_registry import ToolRegistry

class OwlAICrew(Document):
    def kickoff(self):
        """
        Executes the crew. Created a Run document and returns the result.
        """
        try:
            # 1. Create Run Document
            run_doc = frappe.get_doc({
                "doctype": "OwlAI Crew Run",
                "crew": self.name,
                "status": "Running",
                "started_at": frappe.utils.now_datetime()
            })
            run_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            
            tool_registry = ToolRegistry()
            
            # 2. Initialize Agents
            crew_agents = []
            agent_map = {} # map agent_name -> Agent object
            
            for agent_link in self.agents:
                frappe_agent = frappe.get_doc("OwlAI Agent", agent_link.agent)
                
                # Tools
                agent_tools = []
                for t in frappe_agent.tools:
                    # tool_registry.get_crewai_tool returns a crewai.Tool
                    crew_tool = tool_registry.get_crewai_tool(t.tool_name) 
                    if crew_tool:
                        agent_tools.append(crew_tool)
                
                # LLM
                llm = get_llm(frappe_agent.model)
                if not llm:
                    frappe.throw(f"Model not configured for agent {frappe_agent.name}")
                
                # Create CrewAI Agent
                agent_obj = Agent(
                    role=frappe_agent.agent_role,
                    goal=frappe_agent.goal,
                    backstory=frappe_agent.backstory,
                    verbose=frappe_agent.verbose,
                    allow_delegation=frappe_agent.allow_delegation,
                    tools=agent_tools,
                    llm=llm
                )
                crew_agents.append(agent_obj)
                agent_map[frappe_agent.name] = agent_obj
                
            # 3. Initialize Tasks
            crew_tasks = []
            task_map = {} # map task_name to Task Object (not implementing yet, using task linking)
            
            # Sort tasks? They are in child table order.
            
            for task_link in self.tasks:
                frappe_task = frappe.get_doc("OwlAI Task", task_link.task)
                
                assigned_agent = agent_map.get(frappe_task.agent)
                if not assigned_agent:
                     frappe.throw(f"Agent {frappe_task.agent} not found in this crew for task {frappe_task.name}")
                
                # Context (Dependencies)
                context_tasks = []
                if frappe_task.context:
                    for ctx in frappe_task.context:
                        # ctx.task is the Name of the OwlAI Task
                        # We need to find the Corresponding CrewAI Task Object
                        # This assumes the dependency task was already processed (ordered list)
                        # We need to map OwlAI Task Name -> CrewAI Task Object
                        pass 
                        # This is tricky because task_map needs to use the task NAME (ID)
                        # and we are iterating. If dependency is later in list, it fails.
                        # CrewAI usually handles context by passing list of Task objects.
                
                task_obj = Task(
                    description=frappe_task.description,
                    expected_output=frappe_task.expected_output,
                    agent=assigned_agent,
                    async_execution=frappe_task.async_execution
                    # context=... (Implementing context requires solving the mapping)
                )
                
                crew_tasks.append(task_obj)
                # Store for context resolution if needed later
                task_map[frappe_task.name] = task_obj

            # Re-loop to resolve context if we want to be robust, 
            # but current structure implies we might miss forward refs.
            # CrewAI Context expects list of Task objects.
            
            for i, task_link in enumerate(self.tasks):
                frappe_task = frappe.get_doc("OwlAI Task", task_link.task)
                if frappe_task.context:
                    ctx_objs = []
                    for ctx in frappe_task.context:
                         # Find the task object corresponding to ctx.task
                         if ctx.task in task_map:
                             ctx_objs.append(task_map[ctx.task])
                    
                    if ctx_objs:
                        crew_tasks[i].context = ctx_objs
            
            # 4. Initialize Crew
            manager_llm = None
            if self.execution_process == "Hierarchical" and self.manager_agent:
                manager_doc = frappe.get_doc("OwlAI Agent", self.manager_agent)
                manager_llm = get_llm(manager_doc.model)
                
            crew = Crew(
                agents=crew_agents,
                tasks=crew_tasks,
                process=Process.hierarchical if self.execution_process == "Hierarchical" else Process.sequential,
                manager_llm=manager_llm,
                verbose=self.verbose,
                planning=self.planning,
                memory=self.memory
            )
            
            # 5. Kickoff
            result = crew.kickoff()
            
            # 6. Update Run
            run_doc.db_set("status", "Completed")
            run_doc.db_set("result", str(result))
            run_doc.db_set("completed_at", frappe.utils.now_datetime())
            # For full output, we might need to capture stdout/logs or use callbacks.
            # For now result is enough.
            
            return str(result)
            
        except Exception as e:
            frappe.log_error(f"Crew Execution Failed: {str(e)}")
            if 'run_doc' in locals():
                run_doc.db_set("status", "Failed")
                run_doc.db_set("full_output", str(e))
                run_doc.db_set("completed_at", frappe.utils.now_datetime())
            raise e

@frappe.whitelist()
def run_crew(crew_name):
    """
    Public API to run a crew.
    """
    crew = frappe.get_doc("OwlAI Crew", crew_name)
    return crew.kickoff()
