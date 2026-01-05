from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import frappe
from tb_owlai_core.plugins.base import BaseTool

class MapsSchema(BaseModel):
    doctype: str = Field(..., description="DocType to navigate to (e.g. 'Sales Order')")
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
        doctype = arguments.get("doctype")
        view = arguments.get("view", "List")
        filters = arguments.get("filters")

        if not frappe.db.exists("DocType", doctype):
            return {"error": f"DocType '{doctype}' not found."}

        if not frappe.has_permission(doctype, "read"):
            return {"error": f"Insufficient permissions for {doctype}"}

        # Construct Action for Frontend
        return {
            "action": "navigate",
            "doctype": doctype,
            "view": view,
            "route_options": filters,
            "message": f"Opening {doctype} {view}..."
        }
