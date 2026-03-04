from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool


class EnsureExistsSchema(BaseModel):
    doctype: str = Field(..., description="The DocType to search or create (e.g. 'Customer', 'Item')")
    search_value: str = Field(..., description="Value to search for (matched against name and common display fields)")
    data: Optional[Dict[str, Any]] = Field(None, description="Field values to use when creating a new record if not found")


class EnsureExistsTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "ensure_exists"
        self.description = "Get an existing record by search value, or create it if it does not exist. Returns the record name and whether it was newly created."
        self.category = "Document Management"
        self.args_schema = EnsureExistsSchema

    def _get_display_fields(self, doctype: str) -> list:
        """Get common display/title fields for a DocType."""
        common_fields = [
            f"{doctype.lower().replace(' ', '_')}_name",
            "title",
            "subject",
            "full_name",
            "item_name",
            "customer_name",
            "supplier_name",
            "employee_name",
            "lead_name",
        ]
        try:
            meta = frappe.get_meta(doctype)
            existing = {f.fieldname for f in meta.fields}
            return [f for f in common_fields if f in existing]
        except Exception:
            return []

    def _find_record(self, doctype: str, search_value: str) -> Optional[str]:
        """Search for a record by name or common display fields. Returns record name or None."""
        if frappe.db.exists(doctype, search_value):
            return search_value

        display_fields = self._get_display_fields(doctype)
        for field in display_fields:
            try:
                result = frappe.db.get_value(doctype, {field: search_value}, "name")
                if result:
                    return result
            except Exception:
                pass

        try:
            result = frappe.db.sql("""
                SELECT name FROM `tab{doctype}`
                WHERE name LIKE %(pattern)s
                LIMIT 1
            """.format(doctype=doctype),
                {"pattern": f"%{search_value}%"}, as_dict=True)
            if result:
                return result[0]["name"]
        except Exception:
            pass

        return None

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        search_value = arguments.get("search_value")
        data = arguments.get("data") or {}

        if not frappe.has_permission(doctype, "read"):
            return {"error": f"Permission denied: cannot read {doctype}"}

        existing_name = self._find_record(doctype, search_value)
        if existing_name:
            try:
                doc = frappe.get_doc(doctype, existing_name)
                return {
                    "name": existing_name,
                    "doctype": doctype,
                    "created": False,
                    "message": f"Found existing {doctype}: {existing_name}",
                    "data": doc.as_dict(),
                }
            except Exception as e:
                return {"error": f"Found record '{existing_name}' but could not fetch it: {str(e)}"}

        if not frappe.has_permission(doctype, "create"):
            return {"error": f"Permission denied: cannot create {doctype}"}

        creation_data = dict(data)
        if "name" not in creation_data:
            display_fields = self._get_display_fields(doctype)
            if display_fields:
                for field in display_fields:
                    if field not in creation_data:
                        creation_data[field] = search_value
                        break
            else:
                creation_data["name"] = search_value

        try:
            doc = frappe.get_doc({"doctype": doctype, **creation_data})
            doc.insert(ignore_permissions=False)
            frappe.db.commit()
            return {
                "name": doc.name,
                "doctype": doctype,
                "created": True,
                "message": f"Created new {doctype}: {doc.name}",
                "data": doc.as_dict(),
            }
        except Exception as e:
            frappe.db.rollback()
            return {"error": f"Failed to create {doctype}: {str(e)}"}
