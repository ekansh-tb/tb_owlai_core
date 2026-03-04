from pydantic import BaseModel, Field
from typing import Dict, Any
import frappe
from tb_owlai_core.plugins.base import BaseTool

class GetDocumentSchema(BaseModel):
    doctype: str = Field(..., description="DocType name")
    name: str = Field(..., description="Document ID/Name")

class GetDocument(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_document"
        self.description = "Fetch specific details of a document. Requires document 'name' (ID)."
        self.category = "Core Operations"
        self.args_schema = GetDocumentSchema

    # Fields that must never be sent to the LLM
    SENSITIVE_FIELDS = {"password", "api_key", "api_secret", "secret", "token",
                        "new_password", "reset_password_key", "auth_token",
                        "session_key", "api_token"}

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        name = arguments.get("name")

        if not frappe.db.exists(doctype, name):
             return {"error": f"{doctype} '{name}' not found."}

        if not frappe.has_permission(doctype, "read", doc=name):
             return {"error": f"Permission denied for {doctype} '{name}'"}

        try:
            doc = frappe.get_doc(doctype, name)
            # Redact sensitive fields before sending to LLM
            d = doc.as_dict()
            meta = frappe.get_meta(doctype)
            password_fields = {f.fieldname for f in meta.fields if f.fieldtype == "Password"}
            redact = self.SENSITIVE_FIELDS | password_fields
            return {k: "[REDACTED]" if k in redact else v for k, v in d.items()}
        except Exception as e:
            return {"error": str(e)}
