from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool

class NavigateSchema(BaseModel):
    doctype: str = Field(..., description="The DocType or Page name to navigate to (e.g. 'Sales Order', 'Workspaces', 'Dashboard').")
    docname: Optional[str] = Field(None, description="The specific document ID/name to open (e.g. 'SO-001').")
    view: Optional[str] = Field("List", description="The view type (List, Form, Report, Dashboard, Kanban, Tree).")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters to apply to the list view.")

class NavigateTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "navigate"
        self.description = "Navigate the user to a specific DocType (List/Form), standard Page, Report, or Dashboard in Frappe Desk. Use this for 'Show', 'Open', 'Go to' commands."
        self.category = "Navigation"
        self.args_schema = NavigateSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        target = arguments.get("doctype")
        view = arguments.get("view", "List")
        docname = arguments.get("docname")
        filters = arguments.get("filters")
        
        if not target:
            return {"error": "Target DocType or Page name is required."}

        # Fuzzy Search logic
        found_doctype = None
        if frappe.db.exists("DocType", target):
            found_doctype = target
        else:
            clean_name = target.replace(" List", "").replace(" Page", "")
            if frappe.db.exists("DocType", clean_name):
                 found_doctype = clean_name
            else:
                 fuzzy = frappe.db.get_value("DocType", {"name": ["like", f"%{clean_name}%"]}, "name")
                 if fuzzy: found_doctype = fuzzy

        if found_doctype:
            target = found_doctype
            if not frappe.has_permission(target, "read"):
                return {"message": f"I cannot navigate to {target} because you do not have permission."}
            # If docname is provided, it's definitely a Form view
            if docname:
                view = "Form"
        
        elif frappe.db.exists("Page", target):
            view = "Page"
        
        # Return action for frontend — detected by engine via result["action"]
        return {
            "action": "navigate",
            "message": f"Navigated to {target}.",
            "doctype": target,
            "docname": docname,
            "view": view,
            "filters": filters,
        }
