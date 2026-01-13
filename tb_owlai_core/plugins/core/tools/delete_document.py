from pydantic import BaseModel, Field
from typing import Any, Dict
import frappe
from tb_owlai_core.plugins.base import BaseTool

class DeleteDocumentSchema(BaseModel):
    doctype: str = Field(..., description="DocType name")
    name: str = Field(..., description="Document ID/Name")

class DeleteDocument(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "delete_document"
        self.description = "Delete a document. This action cannot be undone."
        self.category = "Core Operations"
        self.args_schema = DeleteDocumentSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        name = arguments.get("name")

        if not frappe.db.exists(doctype, name):
             return {"error": f"{doctype} '{name}' not found."}

        # Permission Check
        if not frappe.has_permission(doctype, "delete", doc=name):
             return {"error": f"Permission denied to delete {doctype} '{name}'"}

        try:
            frappe.delete_doc(doctype, name)
            frappe.db.commit()
            return {"status": "Deleted", "message": f"{doctype} '{name}' deleted."}
        except Exception as e:
            return {"error": str(e)}
