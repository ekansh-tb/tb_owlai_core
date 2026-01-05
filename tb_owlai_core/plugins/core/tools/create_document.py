from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool

class CreateDocumentSchema(BaseModel):
    doctype: str = Field(..., description="DocType name (e.g., 'Task', 'Customer')")
    data: Dict[str, Any] = Field(..., description="Fields and values. Child tables as list of dicts.")
    submit: bool = Field(False, description="Submit after creation?")
    validate_only: bool = Field(False, description="Validate without saving?")

class CreateDocument(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "create_document"
        self.description = "Create a new document. Supports child tables (list of dicts). Referenced records must exist."
        self.category = "Core Operations"
        self.args_schema = CreateDocumentSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        data = arguments.get("data", {})
        submit = arguments.get("submit", False)
        validate_only = arguments.get("validate_only", False)

        if not frappe.db.exists("DocType", doctype):
            return {"error": f"DocType '{doctype}' does not exist."}

        # Heuristic: Map 'title' to 'description' if 'title' is not a valid field but 'description' is mandatory and missing
        # This fixes common LLM hallucinations for simple DocTypes like ToDo
        try:
            meta = frappe.get_meta(doctype)
            if "title" in data and not meta.has_field("title") and meta.has_field("description"):
                description_field = meta.get_field("description")
                if description_field.reqd and not data.get("description"):
                    data["description"] = data.pop("title")
        except Exception:
            pass # Ignore meta errors here, will catch later

        # Permission Check
        if not frappe.has_permission(doctype, "create"):
             return {"error": f"You do not have permission to create '{doctype}'."}

        try:
            doc = frappe.new_doc(doctype)
            
            # Populate fields
            for key, value in data.items():
                if isinstance(value, list): # Likely child table
                    for row in value:
                        doc.append(key, row)
                else:
                    if hasattr(doc, key):
                        setattr(doc, key, value)
            
            # Set name if provided (for manual naming)
            if "name" in data and not doc.name:
                doc.name = data["name"]

            if validate_only:
                doc.validate()
                return {"status": "valid", "message": "Validation successful"}

            doc.insert(ignore_permissions=True) # Permissions checked above

            if submit and doc.docstatus == 0 and doc.meta.is_submittable:
                if frappe.has_permission(doctype, "submit", doc=doc.name):
                    doc.submit()
                else:
                    return {
                        "name": doc.name, 
                        "warning": "Document created but submit permission denied."
                    }

            frappe.db.commit()
            
            return {
                "name": doc.name,
                "doctype": doc.doctype,
                "status": "Submitted" if doc.docstatus == 1 else "Saved",
                "message": f"Created {doctype}: {doc.name}"
            }

        except Exception as e:
            frappe.log_error(f"Create Document Error: {str(e)}")
            return {"error": str(e)}
