from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import frappe
import frappe.utils
from tb_owlai_core.plugins.base import BaseTool

class FrappeUtilsSchema(BaseModel):
    function: str = Field(..., description="The function name to call.", enum=[
        "format_date", "money_in_words", "validate_email_address", 
        "now", "today", "add_days", "add_months", "get_url", 
        "flt", "cint", "cstr", "get_first_day", "get_last_day"
    ])
    args: Optional[List[Any]] = Field(default=[], description="Positional arguments for the function.")
    kwargs: Optional[Dict[str, Any]] = Field(default={}, description="Keyword arguments for the function.")

class FrappeUtilsTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "frappe_utils"
        self.description = "Access standard Frappe utility functions for dates, math, formatting, etc."
        self.category = "Utilities"
        self.args_schema = FrappeUtilsSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        func_name = arguments.get("function")
        args = arguments.get("args", [])
        kw_args = arguments.get("kwargs", {})
        
        allowed_functions = [
            "format_date", "money_in_words", "validate_email_address", 
            "now", "today", "add_days", "add_months", "get_url", 
            "flt", "cint", "cstr", "get_first_day", "get_last_day"
        ]
        
        if func_name not in allowed_functions:
             return {"error": f"Function '{func_name}' is not allowed or supported."}
             
        try:
            # Dynamically get from frappe.utils
            if hasattr(frappe.utils, func_name):
                func = getattr(frappe.utils, func_name)
                # Some functions might be in frappe.utils.data or other submodules imported in utils
                # But getattr(frappe.utils, ...) usually works for exposed ones.
                
                result = func(*args, **kw_args)
                return {"result": result}
            else:
                 return {"error": f"Function '{func_name}' not found in frappe.utils."}
        except Exception as e:
            return {"error": str(e)}
