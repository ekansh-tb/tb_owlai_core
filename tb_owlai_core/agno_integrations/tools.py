
from typing import Optional, Union, Any, List, Dict
import json
import ast
from agno.tools import Toolkit
from tb_owlai_core.tool_registry import ToolRegistry
import frappe

class FrappeToolkit(Toolkit):
    def __init__(self, selected_tools: Optional[List[str]] = None):
        super().__init__(name="frappe_toolkit")
        self.registry = ToolRegistry() # Instantiate
        
        # Tool Name mapping to Method
        # Note: Tool names must match what is in 'OwlAI Tool' / 'ToolRegistry' keys if we want consistency
        # Or we map UI names to these methods.
        # Assuming UI selection passes "list_documents", "get_document" etc.
        
        tool_map = {
            "get_doctype_info": self.get_doctype_schema,
            "list_documents": self.list_documents,
            "get_document": self.get_document,
            "create_document": self.create_document,
            "update_document": self.update_document,
            "delete_document": self.delete_document,
            "navigate": self.navigate,
            "search_documents": self.search_documents,
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
            doctype (str): The name of the DocType (e.g. 'Task', 'Sales Order').

        Returns:
            dict: Schema information including fields and permissions.
        """
        return self._exec("get_doctype_info", doctype=doctype)

    def list_documents(self, doctype: str, filters: Optional[Union[dict, str]] = None, fields: Optional[Union[list, str]] = None, limit_page_length: int = 20) -> list:
        """
        Fetch a list of documents for a given DocType.

        Args:
            doctype (str): The DocType to list.
            filters (dict): Optional filters (e.g., {"status": "Open"}).
            fields (list): Optional list of fields to fetch.
            limit_page_length (int): Max number of records to return. Default 20.

        Returns:
            list: A list of document dictionaries.
        """
        parsed_filters = self._parse_dict(filters)
        parsed_fields = self._parse_list(fields)
        return self._exec("list_documents", doctype=doctype, filters=parsed_filters, fields=parsed_fields, limit_page_length=limit_page_length)

    def get_document(self, doctype: str, name: str) -> dict:
        """
        Get a specific document by name.

        Args:
            doctype (str): The DocType name.
            name (str): The document name (ID).

        Returns:
            dict: The full document content.
        """
        return self._exec("get_document", doctype=doctype, name=name)

    def create_document(self, doctype: str, data: dict) -> dict:
        """
        Create a new document.

        Args:
            doctype (str): The DocType to create.
            data (dict): The fields and values for the new document.

        Returns:
            dict: The created document.
        """
        return self._exec("create_document", doctype=doctype, data=data)

    def update_document(self, doctype: str, name: str, data: dict) -> dict:
        """
        Update an existing document.

        Args:
            doctype (str): The DocType.
            name (str): The document name.
            data (dict): The fields to update.

        Returns:
            dict: The updated document.
        """
        return self._exec("update_document", doctype=doctype, name=name, data=data)

    def delete_document(self, doctype: str, name: str) -> str:
        """
        Delete a document.

        Args:
            doctype (str): The DocType.
            name (str): The document name.

        Returns:
            str: Success message.
        """
        return self._exec("delete_document", doctype=doctype, name=name)

    def navigate(self, doctype: str, view: str = "List", filters: Optional[Union[dict, str]] = None) -> dict:
        """
        Navigate the user to a specific DocType list or page in the Frappe Desk.

        Args:
            doctype (str): The DocType to navigate to.
            view (str): The view type (List, Report, Dashboard, Kanban, Tree). Default is 'List'.
            filters (dict): Optional filters to apply to the view (e.g. {"status": "Open"}).

        Returns:
            dict: Action payload for the frontend.
        """
        parsed_filters = self._parse_dict(filters)
        return self._exec("navigate", doctype=doctype, view=view, filters=parsed_filters)

    def search_documents(self, query: str, doctype: Optional[str] = None) -> list:
        """
        Global search or search within a specific DocType.

        Args:
            query (str): The search term.
            doctype (str): Optional DocType to restrict search.

        Returns:
            list: Search results.
        """
        return self._exec("search_documents", query=query, doctype=doctype)
        
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
