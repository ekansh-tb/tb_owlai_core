import frappe
from tb_owlai_core.plugins.base import BaseTool

class NavigateTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="navigate",
            description="Navigate the user to a specific DocType list or page in the Frappe Desk. Use this when the user asks to 'Show' or 'Go to' a list or page.",
            category="Navigation",
            inputSchema={
                "type": "object",
                "properties": {
                    "doctype": {
                        "type": "string",
                        "description": "The DocType to navigate to (e.g. Sales Order, Task, Item)."
                    },
                    "view": {
                        "type": "string",
                        "description": "The view type (List, Report, Dashboard, Kanban, Tree). Default is List.",
                        "enum": ["List", "Report", "Dashboard", "Kanban", "Tree"]
                    }
                },
                "required": ["doctype"]
            }
        )

    def execute(self, **kwargs):
        doctype = kwargs.get('doctype')
        view = kwargs.get('view', 'List')
        
        # 1. Permission Check
        if not frappe.db.exists("DocType", doctype):
             return {"error": f"DocType '{doctype}' not found."}
             
        if not frappe.has_permission(doctype, "read"):
             return {"message": f"I cannot navigate to {doctype} because you do not have read permissions for it."}

        # 2. Return Action for Client
        return {
            "action": "navigate",  # Signals owl_chat.js to call frappe.set_route
            "message": f"Navigating to {doctype}...",
            "doctype": doctype,
            "view": view
        }
