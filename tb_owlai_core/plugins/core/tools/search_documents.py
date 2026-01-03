from typing import Any, Dict
import frappe
from tb_owlai_core.plugins.base import BaseTool

class SearchDocuments(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "search_documents"
        self.description = "Search for documents. If doctype is provided, searches that doctype. Otherwise uses global search. Supports generic filters."
        self.category = "Search"
        self.inputSchema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to search for"},
                "doctype": {"type": "string", "description": "Optional: Restrict to DocType"},
                "filters": {"type": "object", "description": "Optional: Additional filters if doctype is provided"}
            },
            "required": ["query"]
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = arguments.get("query")
        doctype = arguments.get("doctype")
        filters = arguments.get("filters", {})

        try:
            if doctype:
                # Targeted search on a DocType
                if not frappe.has_permission(doctype, "read"):
                    return {"error": f"Permission denied for {doctype}"}
                
                # Combine query with filters if possible, or just used filters
                # Usually standard search uses 'name like %query%' or 'title like %query%'
                or_filters = []
                if query:
                    meta = frappe.get_meta(doctype)
                    search_fields = [f.fieldname for f in meta.fields if f.search_index]
                    if not search_fields:
                        search_fields = ["name"]
                        if meta.title_field: search_fields.append(meta.title_field)
                    
                    for field in search_fields:
                        or_filters.append([field, "like", f"%{query}%"])
                
                data = frappe.get_list(
                    doctype,
                    filters=filters,
                    or_filters=or_filters if or_filters else None,
                    fields=["name", "modified"],
                    limit_page_length=20
                )
                
                return {
                    "doctype": doctype,
                    "data": data,
                    "action": "list", # Trigger list view
                    "filters": filters
                }

            else:
                # Global Search using frappe.utils.global_search
                # This doesn't support generic filters well, but we can return matches
                results = frappe.utils.global_search.search(query)
                formatted_results = []
                for res in results:
                     formatted_results.append({
                         "doctype": res.doctype,
                         "name": res.name,
                         "content": res.content
                     })
                
                return {
                    "data": formatted_results,
                    "action": "list", # Maybe a generic search result view?
                    "message": f"Global search results for '{query}'"
                }

        except Exception as e:
            return {"error": str(e)}
