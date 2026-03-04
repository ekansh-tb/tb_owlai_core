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

    # Fields that must never be returned to the LLM
    SENSITIVE_FIELDS = {"password", "api_key", "api_secret", "secret", "token",
                        "new_password", "reset_password_key", "auth_token",
                        "session_key", "api_token"}

    def _safe_dict(self, doc):
        """Return doc dict with sensitive fields redacted."""
        d = doc.as_dict()
        return {k: "[REDACTED]" if k in self.SENSITIVE_FIELDS else v for k, v in d.items()}

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        action = arguments.get("action")
        doctype = arguments.get("doctype")
        filters = arguments.get("filters")
        fields = arguments.get("fields", ["name", "modified"])
        doc_data = arguments.get("doc")
        name = arguments.get("name")
        limit = arguments.get("limit_page_length", 20)

        # Never return fields=["*"] — restrict to safe defaults
        if fields == ["*"]:
            fields = ["name", "modified", "modified_by", "creation"]

        try:
            if action == "get_list":
                if not frappe.has_permission(doctype, "read"):
                    return {"error": f"Permission denied to list {doctype}"}
                return {"result": frappe.get_list(doctype, filters=filters, fields=fields, limit_page_length=limit)}

            elif action == "get_doc":
                if not name and not filters:
                    return {"error": "Name or filters required for get_doc"}
                if not frappe.has_permission(doctype, "read", doc=name):
                    return {"error": f"Permission denied for {doctype} '{name}'"}
                doc = frappe.get_doc(doctype, name if name else filters)
                return {"result": self._safe_dict(doc)}

            elif action == "insert":
                if not frappe.has_permission(doctype, "create"):
                    return {"error": f"Permission denied to create {doctype}"}
                if not doc_data:
                    return {"error": "Document data required for insert"}
                doc_data["doctype"] = doctype
                d = frappe.get_doc(doc_data)
                d.insert()
                return {"result": self._safe_dict(d)}

            elif action == "update":
                if not name:
                    return {"error": "Name required for update"}
                if not frappe.has_permission(doctype, "write", doc=name):
                    return {"error": f"Permission denied to update {doctype} '{name}'"}
                if not doc_data:
                    return {"error": "Data to update required"}
                d = frappe.get_doc(doctype, name)
                d.update(doc_data)
                d.save()
                return {"result": self._safe_dict(d)}

            elif action == "delete":
                if not name:
                    return {"error": "Name required for delete"}
                if not frappe.has_permission(doctype, "delete", doc=name):
                    return {"error": f"Permission denied to delete {doctype} '{name}'"}
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
