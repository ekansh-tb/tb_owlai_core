import json
import ast
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from agno.tools import Toolkit
from tb_owlai_core.tool_registry import ToolRegistry

class GetDoctypeSchemaArgs(BaseModel):
    doctype: str = Field(..., description="The name of the DocType (e.g. 'Task', 'Sales Order').")

class NavigateArgs(BaseModel):
    doctype: str = Field(..., description="The DocType or Page Name to navigate to (e.g. 'Sales Order', 'Workspaces').")
    view: str = Field("List", description="The view type (List, Form, Page, Report, Dashboard, Kanban, Tree).")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters to apply/preset. Use {'name': 'DOC-ID'} for Form view.")

class WebSearchArgs(BaseModel):
    query: str = Field(..., description="The query to search the internet for.")


class ListDocumentsArgs(BaseModel):
    doctype: str = Field(..., description="The DocType to fetch.")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters as a dictionary.")
    fields: Optional[List[str]] = Field(None, description="Fields to retrieve.")
    limit_page_length: int = Field(20, description="Number of records to return.")

class SearchDocumentsArgs(BaseModel):
    query: str = Field(..., description="The search string.")
    doctype: Optional[str] = Field(None, description="Optional DocType to restrict search to.")

class SearchKnowledgeBaseArgs(BaseModel):
    query: str = Field(..., description="The natural language query for documentation and policies.")

class GetDocumentArgs(BaseModel):
    doctype: str = Field(..., description="The DocType of the document.")
    name: str = Field(..., description="The unique name (ID) of the document.")

class FrappeToolkit(Toolkit):
    def __init__(self, selected_tools: Optional[List[str]] = None):
        super().__init__(name="frappe_toolkit")
        self.registry = ToolRegistry() # Instantiate
        
        # Tool Name mapping to Method
        tool_map = {
            "get_doctype_info": self.get_doctype_schema,
            "list_documents": self.list_documents,
            "get_document": self.get_document,
            "create_document": self.create_document,
            "update_document": self.update_document,
            "delete_document": self.delete_document,
            "navigate": self.navigate,
            "search_documents": self.search_documents,
            "search_knowledge_base": self.search_knowledge_base,
            "web_search": self.web_search,
            "frappe_utils": self.frappe_utils
        }
        
        if selected_tools:
            for name, func in tool_map.items():
                if name in selected_tools:
                    self.register(func)
        else:
            # Register all by default if no selection
            for func in tool_map.values():
                self.register(func)

    def _exec(self, tool_name: str, **kwargs):
        """Helper to execute tool with proper dictionary arguments"""
        return self.registry.execute(tool_name, kwargs)

    def _parse_dict(self, value: Union[Dict, str, None]) -> Optional[Dict]:
        if value is None: return None
        if isinstance(value, dict): return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                try:
                    return ast.literal_eval(value)
                except:
                    return {}
        return {}

    def _parse_list(self, value: Union[List, str, None]) -> Optional[List]:
        if value is None: return None
        if isinstance(value, list): return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                try:
                    return ast.literal_eval(value)
                except:
                    return []
        return []

    def get_doctype_schema(self, doctype: str) -> dict:
        """
        Get schema information (docfields, permissions) for a specific DocType.
        Use this before creating or updating documents to know which fields are mandatory.

        Args:
            doctype (str): The name of the DocType.
        """
        return self._exec("get_doctype_info", doctype=doctype)


    def navigate(self, doctype: str, view: str = "List", filters: Optional[Union[dict, str]] = None) -> dict:
        """
        Navigate the user to a specific DocType list, form, or a standard Page.
        IMPORTANT: If you have a specific document name or ID, set view="Form" and use filters={"name": "id"}.
        For standard pages (like 'Workspaces', 'Dashboard'), set view="Page" and doctype="PageName".
        
        Args:
            doctype (str): The DocType or Page Name.
            view (str): The view type (List, Form, Page, etc.).
            filters (dict): Optional filters to apply.
        """
        parsed_filters = self._parse_dict(filters)
        
        # Heuristic: If filters contains 'name', it's usually a Form view request
        if parsed_filters and ("name" in parsed_filters or "id" in parsed_filters):
             if view == "List": # Only override if it was default
                 view = "Form"

        return self._exec("navigate", doctype=doctype, view=view, filters=parsed_filters)

    def list_documents(self, doctype: str, filters: Optional[Union[dict, str]] = None, fields: Optional[Union[list, str]] = None, limit_page_length: int = 10) -> List[str]:
        """
        Fetch a list of documents for a given DocType.
        Returns a human-readable list of strings to save tokens and avoid raw JSON spam.
        """
        parsed_filters = self._parse_dict(filters)
        parsed_fields = self._parse_list(fields)
        
        # Determine "Smart Fields" if not provided
        if not parsed_fields:
            if doctype == "Sales Order": parsed_fields = ["name", "customer", "grand_total", "status"]
            elif doctype == "Task": parsed_fields = ["name", "subject", "status", "priority", "exp_end_date"]
            elif doctype == "ToDo": parsed_fields = ["name", "description", "status"]
            else: parsed_fields = ["name"] # Fallback
            
        docs = self._exec("list_documents", doctype=doctype, filters=parsed_filters, fields=parsed_fields, limit_page_length=limit_page_length)
        
        # Format as Strings
        results = []
        if isinstance(docs, list):
            for d in docs:
                # Create a concise summary string
                # e.g. "SO-001 | Customer A | $500 | Pending"
                if isinstance(d, dict):
                     parts = [str(d.get(f, "")).strip() for f in parsed_fields if d.get(f)]
                     results.append(" | ".join(parts))
                else:
                    results.append(str(d))
        
        if not results:
            return ["No documents found."]
            
        return results


    def search_documents(self, query: str, doctype: Optional[str] = None) -> list:
        """
        Global search or search within a specific DocType (Database Search).
        """
        return self._exec("search_documents", query=query, doctype=doctype)
    
    def search_knowledge_base(self, query: str) -> list:
        """
        Search the OwlAI Knowledge Base (Vector Store) for documentation and policies.
        """
        try:
            from tb_owlai_core.agno_integrations.knowledge_index import search_knowledge_base
            return search_knowledge_base(query)
        except Exception as e:
            return [f"Error searching knowledge base: {e}"]
    
    def web_search(self, query: str) -> str:
        """
        Search the web for real-time information.
        Returns a summarized markdown string.
        """
        try:
            from agno.tools.duckduckgo import DuckDuckGoTools
            ddg = DuckDuckGoTools(fixed_max_results=5)
            # DuckDuckGoTools usually has 'duckduckgo_search' method or similar
            # But Agno Toolkit wrappers might differ. 
            # Let's inspect how Agno does it or just use the library directly if easier.
            # safe option: use the library directly if installed, or the tool
            
            try:
                from duckduckgo_search import DDGS
                results = DDGS().text(query, max_results=5)
                if not results:
                    return "No results found."
                
                md_output = "### Search Results\n"
                for i, r in enumerate(results, 1):
                    md_output += f"{i}. **[{r.get('title', 'Link')}]({r.get('href', '#')})**\n   {r.get('body', '')}\n\n"
                return md_output
            except ImportError:
                 return "DuckDuckGo Search library not installed."
                 
        except Exception as e:
            return f"Error performing web search: {e}"
        
    def get_document(self, doctype: str, name: str) -> dict:
        """
        Get all fields of a specific document.
        
        Args:
            doctype (str): The DocType of the document.
            name (str): The name (ID) of the document.
        """
        return self._exec("get_document_v2", doctype=doctype, name=name)

    def create_document(self, doctype: str, properties: Union[dict, str]) -> dict:
        """
        Create a new document.
        Use `get_doctype_info` first to see which fields are required.
        
        Args:
            doctype (str): The DocType to create.
            properties (dict): Fields and values for the new document.
        """
        return self._exec("create_document_v2", doctype=doctype, properties=self._parse_dict(properties))

    def update_document(self, doctype: str, name: str, properties: Union[dict, str]) -> dict:
        """
        Update an existing document.
        
        Args:
            doctype (str): The DocType of the document.
            name (str): The name (ID) of the document to update.
            properties (dict): Fields and values to update.
        """
        return self._exec("update_document_v2", doctype=doctype, name=name, properties=self._parse_dict(properties))

    def delete_document(self, doctype: str, name: str) -> dict:
        """
        Delete a document.
        
        Args:
            doctype (str): The DocType of the document.
            name (str): The name (ID) of the document to delete.
        """
        return self._exec("delete_document_v2", doctype=doctype, name=name)

    def frappe_utils(self, function: str, args: Optional[list] = None, kwargs: Optional[dict] = None) -> dict:
        """
        Call standard Frappe utility functions (formatting, etc.).

        Args:
            function (str): Function name ('format_date', 'money_in_words').
            args (list): Positional arguments.
            kwargs (dict): Keyword arguments.

        Returns:
            dict: Result of the function.
        """
        return self._exec("frappe_utils", function=function, args=args or [], kwargs=kwargs or {})
