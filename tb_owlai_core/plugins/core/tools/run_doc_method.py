from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool

class RunDocMethodSchema(BaseModel):
    doctype: str = Field(..., description="DocType name")
    name: str = Field(..., description="Document Name")
    method: str = Field(..., description="Method name to run (e.g. 'submit', 'cancel')")
    args: Optional[Dict[str, Any]] = Field(None, description="Arguments for the method if needed")

class RunDocMethod(BaseTool):
    args_schema: Optional[type] = RunDocMethodSchema

    def __init__(self):
        super().__init__()
        self.name = "run_doc_method"
        self.description = "Run a method on a document (e.g. submit, cancel, or custom controller methods)."
        self.category = "Core Operations"
        self.args_schema = RunDocMethodSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        name = arguments.get("name")
        method = arguments.get("method")
        args = arguments.get("args") or {}

        if not frappe.db.exists(doctype, name):
            return {"error": f"{doctype} '{name}' not found."}

        # Permission Check (Start with Write, but some methods might need more)
        if not frappe.has_permission(doctype, "write", doc=name):
             return {"error": f"Permission denied for {doctype} '{name}'"}

        try:
            doc = frappe.get_doc(doctype, name)
            
            # Special handling for standard workflow methods
            if method == "submit":
                if not frappe.has_permission(doctype, "submit", doc=name):
                    return {"error": "No Submit Permission"}
                doc.submit()
            elif method == "cancel":
                if not frappe.has_permission(doctype, "cancel", doc=name):
                    return {"error": "No Cancel Permission"}
                doc.cancel()
            else:
                 # Generic method call
                 if hasattr(doc, method):
                     func = getattr(doc, method)
                     # Check if callable
                     if callable(func):
                         # We might want to restrict which methods can be called for security
                         # For now, we trust the agent + write permission + framework whitelisting (if applicable)
                         # but here we are calling Python directly, so we are bypassing whitelist check.
                         # This is powerful.
                         result = func(**args)
                         return {"status": "success", "result": result, "docstatus": doc.docstatus}
                     else:
                         return {"error": f"'{method}' is not a callable method on {doctype}"}
                 else:
                     return {"error": f"Method '{method}' not found on {doctype}"}
            
            return {
                "status": "success", 
                "message": f"Executed '{method}' on {doctype} {name}",
                "docstatus": doc.docstatus,
                "action": "reload"
            }

        except Exception as e:
            frappe.log_error(f"Run Doc Method Error: {str(e)}")
            return {"error": str(e)}
