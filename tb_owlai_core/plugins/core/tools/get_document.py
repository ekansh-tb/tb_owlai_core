from typing import Any, Dict
import frappe
from tb_owlai_core.plugins.base import BaseTool

class GetDocument(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "get_document"
        self.description = "Fetch specific details of a document. Requires document 'name' (ID)."
        self.category = "Core Operations"
        self.inputSchema = {
            "type": "object",
            "properties": {
                "doctype": {"type": "string"},
                "name": {"type": "string", "description": "Document ID/Name"}
            },
            "required": ["doctype", "name"]
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        name = arguments.get("name")

        if not frappe.db.exists(doctype, name):
             return {"error": f"{doctype} '{name}' not found."}

        if not frappe.has_permission(doctype, "read", doc=name):
             return {"error": f"Permission denied for {doctype} '{name}'"}

        try:
            doc = frappe.get_doc(doctype, name)
            return doc.as_dict()
        except Exception as e:
            return {"error": str(e)}
