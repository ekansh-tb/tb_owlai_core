from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool

class UpdateDocumentSchema(BaseModel):
    doctype: str = Field(..., description="DocType name")
    name: str = Field(..., description="Document ID/Name")
    data: Dict[str, Any] = Field(..., description="Fields to update")

class UpdateDocument(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "update_document"
        self.description = "Update specific fields of an existing document."
        self.category = "Core Operations"
        self.args_schema = UpdateDocumentSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        name = arguments.get("name")
        data = arguments.get("data", {})

        if not frappe.db.exists(doctype, name):
            return {"error": f"{doctype} '{name}' not found."}

        # Permission Check (Write)
        if not frappe.has_permission(doctype, "write", doc=name):
             return {"error": f"Permission denied to update {doctype} '{name}'"}

        try:
            doc = frappe.get_doc(doctype, name)
            
            if doc.docstatus == 1:
                return {"error": "Cannot update submitted document. You must cancel it first or use related tools."}

            # Update fields
            for key, value in data.items():
                if hasattr(doc, key):
                     setattr(doc, key, value)
            
            doc.save()  # Respects frappe.session.user permissions
            frappe.db.commit()

            slug = doctype.lower().replace(" ", "-")
            return {
                "name": doc.name,
                "doctype": doctype,
                "url": f"/app/{slug}/{doc.name}",
                "status": "Updated",
                "message": f"Updated {doctype} '{name}' successfully."
            }
        except Exception as e:
            frappe.log_error(f"Update Document Error: {str(e)}")
            return {"error": str(e)}
