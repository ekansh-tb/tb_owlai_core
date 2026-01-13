from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool

class NavigateSchema(BaseModel):
    doctype: str = Field(..., description="The DocType to navigate to (e.g. Sales Order, Task, Item).")
    view: Optional[str] = Field("List", description="The view type (List, Report, Dashboard, Kanban, Tree).", enum=["List", "Report", "Dashboard", "Kanban", "Tree"])

class NavigateTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "navigate"
        self.description = "Navigate the user to a specific DocType list or page in the Frappe Desk. Use this when the user asks to 'Show' or 'Go to' a list or page."
        self.category = "Navigation"
        self.args_schema = NavigateSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        view = arguments.get("view", "List")
        
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
