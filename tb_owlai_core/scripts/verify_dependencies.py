
import frappe
from tb_owlai_core.crewai_integrations.task_adapter import TaskAdapter

def execute():
    frappe.db.rollback() # Start clean

    print("--- Verifying CrewAI Task Dependencies ---")

    # 1. Create Test Agent
    if not frappe.db.exists("OwlAI Agent", "Test Dependency Agent"):
        agent = frappe.new_doc("OwlAI Agent")
        agent.agent_name = "Test Dependency Agent"
        agent.goal = "Test dependencies"
        agent.backstory = "I am a test agent."
        agent.model = "llama3.2:3b-Ollama" # Assumption, or fetch dynamic
        agent.insert()
    
    # 2. Create Task A (The Predecessor)
    if not frappe.db.exists("OwlAI Task", "TASK-DEP-A"):
        t1 = frappe.new_doc("OwlAI Task")
        t1.description = "Task A"
        t1.expected_output = "Output A"
        t1.agent = "Test Dependency Agent"
        t1.insert()
        # Force name for reliability in this script, usually handled by autoname
        # t1.name = "TASK-DEP-A" 
        # frappe.db.set_value... actually let's just rely on the returned name
        t1_name = t1.name
    else:
        t1_name = frappe.db.get_value("OwlAI Task", {"description": "Task A"}, "name")

    print(f"Task A Created: {t1_name}")

    # 3. Create Task B (The Successor)
    if not frappe.db.exists("OwlAI Task", "TASK-DEP-B"):
        t2 = frappe.new_doc("OwlAI Task")
        t2.description = "Task B"
        t2.expected_output = "Output B"
        t2.agent = "Test Dependency Agent"
        t2.append("context", {
            "task": t1_name
        })
        t2.insert()
        t2_name = t2.name
    else:
        t2_name = frappe.db.get_value("OwlAI Task", {"description": "Task B"}, "name")
    
    print(f"Task B Created: {t2_name} | Depends on: {t1_name}")

    # 4. Use Adapter to convert to CrewAI Objects
    adapter = TaskAdapter()
    
    # We must fetch t2 first to see if it pulls t1 correctly into context
    # Note: Adapter caches objects, so doing it in this session should work.
    
    print("Converting Task B to CrewAI Object...")
    crew_task_b = adapter.get_task(t2_name)
    
    print(f"CrewAI Task B Object: {crew_task_b}")
    print(f"Context: {crew_task_b.context}")

    # 5. Verification
    if crew_task_b.context:
        # Check if the context contains a Task object corresponding to Task A
        # Since we don't have the original CrewAI object for A yet (unless recursively created),
        # we check the description/expected_output which matches.
        dep_task = crew_task_b.context[0]
        if dep_task.description == "Task A":
            print("SUCCESS: Context correctly contains Task A.")
        else:
            print(f"FAILURE: Context contains unexpected task: {dep_task.description}")
    else:
        print("FAILURE: Context is empty.")

    frappe.db.rollback() # Cleanup

