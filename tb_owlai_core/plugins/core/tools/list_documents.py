from pydantic import BaseModel, Field, AliasChoices
from typing import Any, Dict, List, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool

class ListDocumentsSchema(BaseModel):
    doctype: str = Field(..., description="DocType name", validation_alias=AliasChoices("doc_type", "DocType", "doctype"))
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Key-value filters (e.g. {'status': 'Open'})")
    fields: Optional[List[str]] = Field(default=["name", "modified", "modified_by", "owner"], description="Fields to fetch")
    limit_start: Optional[int] = Field(0, description="Start index")
    limit_page_length: Optional[int] = Field(20, description="Number of records to fetch")
    order_by: Optional[str] = Field("modified desc", description="Order by field")

class ListDocuments(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "list_documents"
        self.description = "List documents of a specific DocType. Supports generic filtering (kwargs)."
        self.category = "Core Operations"
        self.args_schema = ListDocumentsSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doctype = arguments.get("doctype")
        filters = arguments.get("filters", {})
        fields = arguments.get("fields", ["name", "modified", "modified_by", "owner"])
        limit_start = arguments.get("limit_start", 0)
        limit_page_length = arguments.get("limit_page_length", 20)
        order_by = arguments.get("order_by", "modified desc")

        # Permission Check (Read)
        if not frappe.has_permission(doctype, "read"):
             return {"error": f"Permission denied to list {doctype}"}

        try:
            data = frappe.get_list(
                doctype,
                filters=filters,
                fields=fields,
                limit_start=limit_start,
                limit_page_length=limit_page_length,
                order_by=order_by
            )
            slug = doctype.lower().replace(" ", "-")
            for item in data:
                if 'name' in item:
                    item['url'] = f"/app/{slug}/{item['name']}"
            
            return {
                "doctype": doctype,
                "data": data,
                "filters": filters,
                "count": len(data),
                "action": "list", # Hint for frontend routing
                "message": f"Found {len(data)} {doctype} records."
            }

        except Exception as e:
            return {"error": str(e)}
