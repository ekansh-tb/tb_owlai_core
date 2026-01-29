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
            
            fields_data = []
            skip_types = ["Section Break", "Column Break", "Tab Break", "HTML", "Image", "Fold", "Spacer"]
            
            for df in meta.fields:
                if df.fieldtype not in skip_types and not df.hidden:
                    field_info = {
                        "fieldname": df.fieldname,
                        "label": df.label,
                        "fieldtype": df.fieldtype,
                        "reqd": df.reqd,
                        "options": df.options,
                        "description": df.description
                    }
                    
                    # If it's a child table, get its schema too
                    if df.fieldtype == "Table" and df.options:
                        try:
                            child_meta = frappe.get_meta(df.options)
                            child_fields = []
                            for cdf in child_meta.fields:
                                if cdf.fieldtype not in skip_types and not cdf.hidden:
                                    child_fields.append({
                                        "fieldname": cdf.fieldname,
                                        "label": cdf.label,
                                        "fieldtype": cdf.fieldtype,
                                        "reqd": cdf.reqd
                                    })
                            field_info["child_schema"] = child_fields[:15] # Limit child fields
                        except: pass
                        
                    fields_data.append(field_info)
            
            # Sort: Mandatory fields first
            fields_data.sort(key=lambda x: x['reqd'], reverse=True)

            # Metadata Info
            info = {
                 "title_field": meta.title_field or "name",
                 "is_submittable": meta.is_submittable,
                 "istable": meta.istable,
                 "naming_rule": meta.autoname
            }

            return {
                "doctype": doctype,
                "meta": info,
                "fields": fields_data[:50], # Limit to avoid context overflow
                "message": f"To create a {doctype}, ensure all fields marked 'reqd: True' are provided."
            }
        except Exception as e:
            return {"error": str(e)}
