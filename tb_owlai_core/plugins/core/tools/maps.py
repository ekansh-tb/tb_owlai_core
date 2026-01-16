from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import frappe
from tb_owlai_core.plugins.base import BaseTool

class MapsSchema(BaseModel):
    doctype: Optional[str] = Field(None, description="DocType to navigate to (e.g. 'Sales Order')")
    page: Optional[str] = Field(None, description="Alias for doctype (e.g. 'Task List')")
    view: str = Field("List", description="View type: List, Report, Dashboard, Kanban, Tree")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters to apply (e.g. {'status': 'Open'}).")

class Maps(BaseTool):
    args_schema: Optional[type] = MapsSchema

    def __init__(self):
        super().__init__()
        self.name = "Maps"
        self.description = "Smart Navigation Tool. Use this to open lists, reports, or filtered views."
        self.category = "Navigation"
        self.args_schema = MapsSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype") or arguments.get("page")
        
        if not doctype:
            return {"error": "Please provide a 'doctype' or 'page' argument."}
        view = arguments.get("view", "List")
        filters = arguments.get("filters")

        # 1. Exact Match
        if not frappe.db.exists("DocType", doctype):
            # 2. Try simple heuristic: Remove " List" or " Page"
            clean_name = doctype.replace(" List", "").replace(" Page", "")
            if frappe.db.exists("DocType", clean_name):
                doctype = clean_name
            else:
                # 3. Try to find by name matching
                fuzzy_match = frappe.db.get_value("DocType", {"name": ["like", f"%{clean_name}%"]}, "name")
                if fuzzy_match:
                    doctype = fuzzy_match
                else:
                    return {"error": f"DocType '{doctype}' not found. Please provide a valid DocType name."}

        if not frappe.has_permission(doctype, "read"):
            return {"error": f"Insufficient permissions for {doctype}"}

        # Construct Action for Frontend
        return {
            "action": "navigate",
            "status": "success",
            "doctype": doctype,
            "view": view,
            "route_options": filters,
            "message": f"Successfully navigated to {doctype} {view}."
        }
