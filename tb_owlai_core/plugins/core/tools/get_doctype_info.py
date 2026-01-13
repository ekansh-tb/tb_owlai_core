from pydantic import BaseModel, Field
from typing import Dict, Any
import frappe
from tb_owlai_core.plugins.base import BaseTool

class GetDoctypeInfoSchema(BaseModel):
    doctype: str = Field(..., description="DocType name")

class GetDoctypeInfo(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_doctype_info"
        self.description = "Get schema information for a DocType (fields, types, permissions)."
        self.category = "Metadata"
        self.args_schema = GetDoctypeInfoSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        if not frappe.db.exists("DocType", doctype):
             return {"error": f"DocType '{doctype}' does not exist."}

        try:
            meta = frappe.get_meta(doctype)
            
            # Simple Schema Summary
            fields_data = []
            for df in meta.fields:
                if not df.hidden:
                    fields_data.append({
                        "fieldname": df.fieldname,
                        "label": df.label,
                        "fieldtype": df.fieldtype,
                        "reqd": df.reqd,
                        "options": df.options
                    })
            
            # Sort: Mandatory fields first
            fields_data.sort(key=lambda x: x['reqd'], reverse=True)

            # Permissions
            permissions = {
                "read": frappe.has_permission(doctype, "read"),
                "write": frappe.has_permission(doctype, "write"),
                "create": frappe.has_permission(doctype, "create"),
                "delete": frappe.has_permission(doctype, "delete"),
            }
            
            return {
                "doctype": doctype,
                "fields": fields_data[:60], # Limit to avoid context overflow, but after sorting mandatory first
                "permissions": permissions,
                "is_submittable": meta.is_submittable
            }
        except Exception as e:
            return {"error": str(e)}
