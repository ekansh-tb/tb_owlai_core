from typing import Any, Dict
import frappe
from tb_owlai_core.plugins.base import BaseTool

class GetDoctypeInfo(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_doctype_info"
        self.description = "Get schema information for a DocType (fields, types, permissions)."
        self.category = "Metadata"
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string"}
            },
            "required": ["doctype"]
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        if not frappe.db.exists("DocType", doctype):
             return {"error": f"DocType '{doctype}' does not exist."}

        try:
            meta = frappe.get_meta(doctype)
            
            # Simple Schema Summary
            fields = []
            for df in meta.fields:
                if not df.hidden:
                    fields.append({
                        "fieldname": df.fieldname,
                        "label": df.label,
                        "fieldtype": df.fieldtype,
                        "reqd": df.reqd,
                        "options": df.options
                    })
            
            # Permissions
            permissions = {
                "read": frappe.has_permission(doctype, "read"),
                "write": frappe.has_permission(doctype, "write"),
                "create": frappe.has_permission(doctype, "create"),
                "delete": frappe.has_permission(doctype, "delete"),
            }

            return {
                "doctype": doctype,
                "fields": fields[:60], # Limit to avoid context overflow
                "permissions": permissions,
                "is_submittable": meta.is_submittable
            }
        except Exception as e:
            return {"error": str(e)}
