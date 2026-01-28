
import frappe
from tb_owlai_core.crewai_integrations.crew_manager import CrewManager

@frappe.whitelist()
def run_crew(crew_name, inputs=None):
    """
    API endpoint to run a Crew.
    """
    if isinstance(inputs, str):
        import json
        try:
            inputs = json.loads(inputs)
        except:
            pass # Keep as string or dict
            
    manager = CrewManager()
    try:
        result = manager.run_crew(crew_name, inputs)
        return {"status": "success", "result": str(result)}
    except Exception as e:
        frappe.log_error(f"Crew Execution Error: {crew_name}")
        return {"status": "error", "message": str(e)}
