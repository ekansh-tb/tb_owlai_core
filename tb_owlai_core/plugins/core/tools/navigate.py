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
        target = arguments.get("doctype")
        view = arguments.get("view", "List")
        
        if not target:
            return {"error": "Target DocType or Page name is required."}

        # Fuzzy Search / Logic (borrowed from Maps tool)
        search_target = target
        found_doctype = None
        
        # 1. Exact DocType Match
        if frappe.db.exists("DocType", search_target):
            found_doctype = search_target
        else:
            # 2. Heuristic Cleaning
            clean_name = search_target.replace(" List", "").replace(" Page", "")
            if frappe.db.exists("DocType", clean_name):
                 found_doctype = clean_name
            else:
                 # 3. Fuzzy Match DocType
                 fuzzy = frappe.db.get_value("DocType", {"name": ["like", f"%{clean_name}%"]}, "name")
                 if fuzzy:
                     found_doctype = fuzzy

        final_view = view
        final_target = target

        if found_doctype:
            # It is a DocType
            final_target = found_doctype
            if not frappe.has_permission(final_target, "read"):
                return {"message": f"I cannot navigate to {final_target} because you do not have read permissions for it."}
        
        elif frappe.db.exists("Page", search_target):
            # It is an exact Page match
            final_view = "Page"
            final_target = search_target
        
        else:
             return {"error": f"'{target}' not found. Please provide a valid DocType or Page name."}

        # 3. Return Action for Client
        return {
            "action": "navigate",  # Signals owl_chat.js to call frappe.set_route
            "message": f"Navigating to {target}...",
            "doctype": final_target, # Frontend uses this as the route target
            "view": final_view,
            "filters": arguments.get("filters")
        }
