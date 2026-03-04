from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import frappe
from tb_owlai_core.plugins.base import BaseTool

class FrappeCRUDSchema(BaseModel):
    action: str = Field(..., description="The action to perform: 'get_list', 'get_doc', 'insert', 'update', 'delete', 'get_meta'.", enum=["get_list", "get_doc", "insert", "update", "delete", "get_meta"])
    doctype: str = Field(..., description="The DocType to operate on.")
    filters: Optional[Any] = Field(default=None, description="Filters for get_list or get_doc.")
    fields: Optional[List[str]] = Field(default=["*"], description="Fields to fetch.")
    doc: Optional[Dict[str, Any]] = Field(default=None, description="Document dict for insert/update.")
    name: Optional[str] = Field(default=None, description="Document name for get_doc, update, delete.")
    limit_page_length: Optional[int] = Field(default=20, description="Limit for get_list.")

class FrappeCRUDTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "frappe_crud"
        self.description = "Perform Create, Read, Update, Delete operations on Frappe DocTypes."
        self.category = "System"
        self.args_schema = FrappeCRUDSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        action = arguments.get("action")
        doctype = arguments.get("doctype")
        filters = arguments.get("filters")
        fields = arguments.get("fields", ["*"])
        doc_data = arguments.get("doc")
        name = arguments.get("name")
        limit = arguments.get("limit_page_length", 20)

        try:
            if action == "get_list":
                return {"result": frappe.get_list(doctype, filters=filters, fields=fields, limit_page_length=limit)}

            elif action == "get_doc":
                if not name and not filters:
                    return {"error": "Name or filters required for get_doc"}
                return {"result": frappe.get_doc(doctype, name if name else filters).as_dict()}

            elif action == "insert":
                if not doc_data:
                    return {"error": "Document data required for insert"}
                doc_data["doctype"] = doctype
                d = frappe.get_doc(doc_data)
                d.insert()
                return {"result": d.as_dict()}

            elif action == "update":
                if not name:
                    return {"error": "Name required for update"}
                if not doc_data:
                    return {"error": "Data to update required"}
                d = frappe.get_doc(doctype, name)
                d.update(doc_data)
                d.save()
                return {"result": d.as_dict()}

            elif action == "delete":
                if not name:
                    return {"error": "Name required for delete"}
                frappe.delete_doc(doctype, name)
                return {"result": "Deleted"}
            
            elif action == "get_meta":
                meta = frappe.get_meta(doctype)
                return {"result": {
                    "fields": [f.fieldname for f in meta.fields],
                    "reqd": [f.fieldname for f in meta.fields if f.reqd]
                }}

            else:
                return {"error": f"Unknown action {action}"}
                
        except Exception as e:
            return {"error": str(e)}
