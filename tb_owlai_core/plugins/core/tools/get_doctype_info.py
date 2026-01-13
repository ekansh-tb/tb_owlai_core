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
            # Use cached metadata
            meta = frappe.get_meta(doctype)
            
            # Simple Schema Summary
            fields_data = []
            
            # Standard Standard Field Types to include in summary
            # We skip 'Section Break', 'Column Break' etc as they are UI only
            skip_types = ["Section Break", "Column Break", "Tab Break", "HTML", "Image", "Fold", "Spacer"]
            
            for df in meta.fields:
                if df.fieldtype not in skip_types and not df.hidden:
                    fields_data.append({
                        "fieldname": df.fieldname,
                        "label": df.label,
                        "fieldtype": df.fieldtype,
                        "reqd": df.reqd,
                        "options": df.options
                    })
            
            # Sort: Mandatory fields first
            fields_data.sort(key=lambda x: x['reqd'], reverse=True)

            # Metadata Info
            info = {
                 "title_field": meta.title_field or "name",
                 "description": meta.description,
                 "is_submittable": meta.is_submittable,
                 "istable": meta.istable,
                 "issingle": meta.issingle
            }

            # Permissions
            permissions = {
                "read": frappe.has_permission(doctype, "read"),
                "write": frappe.has_permission(doctype, "write"),
                "create": frappe.has_permission(doctype, "create"),
                "delete": frappe.has_permission(doctype, "delete"),
            }
            
            return {
                "doctype": doctype,
                "meta": info,
                "fields": fields_data[:60], # Limit to avoid context overflow, but after sorting mandatory first
                "permissions": permissions
            }
        except Exception as e:
            return {"error": str(e)}
