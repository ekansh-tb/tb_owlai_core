from typing import Any, Dict
import frappe
from frappe.model.workflow import get_workflow_name, apply_workflow, get_transitions
from tb_owlai_core.plugins.base import BaseTool

class RunWorkflow(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "run_workflow"
        self.description = "Apply a workflow action (e.g. Approve, Reject, Submit) to a document."
        self.category = "Core Operations"
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string"},
                "name": {"type": "string"},
                "action": {"type": "string", "description": "Workflow Action (e.g. 'Approve')"}
            },
            "required": ["doctype", "name", "action"]
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        name = arguments.get("name")
        action = arguments.get("action")

        if not frappe.db.exists(doctype, name):
             return {"error": f"{doctype} '{name}' not found."}

        doc = frappe.get_doc(doctype, name)
        
        # Check if workflow exists
        if not get_workflow_name(doctype):
             return {"error": f"No workflow active for {doctype}."}

        try:
            apply_workflow(doc, action)
            # Commit is handled by apply_workflow usually, but to be safe or if doc.save() wasn't called (it usually is)
            # apply_workflow calls doc.save/submit which commits? No, frappe.desk.form.save calls commit.
            # We should commit.
            frappe.db.commit()
            
            return {
                "status": "Success",
                "message": f"Applied action '{action}' to {doctype} '{name}'. New state: {doc.workflow_state}"
            }
        except Exception as e:
            return {"error": str(e)}
