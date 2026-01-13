import frappe
import inspect
import json
import re
from typing import Any, get_type_hints

def get_function_schema(method_path: str) -> dict:
    """
    Generates an OpenAI-compatible function schema from a Frappe method path.
    Args:
        method_path (str): Dotted path to the function (e.g. 'frappe.client.get_list')
    """
    if not method_path:
        return {}

    try:
        method = frappe.get_attr(method_path)
    except Exception as e:
        frappe.throw(f"Could not find method at path: {method_path}. Error: {str(e)}")

    if not callable(method):
        frappe.throw(f"Object at {method_path} is not callable.")

    sig = inspect.signature(method)
    docstring = inspect.getdoc(method) or ""
    
    # Parse Docstring (Simple extraction of description)
    # We take the first paragraph as description.
    description = docstring.strip().split("\n\n")[0] if docstring else f"Executes {method_path}"

    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    type_hints = get_type_hints(method)

    for param_name, param in sig.parameters.items():
        if param_name in ["self", "cls"]:
            continue
            
        param_schema = {}
        
        # Determine Type
        py_type = type_hints.get(param_name, Any)
        json_type = "string" # Default
        
        if py_type == int: json_type = "integer"
        elif py_type == float: json_type = "number"
        elif py_type == bool: json_type = "boolean"
        elif py_type == dict: json_type = "object"
        elif py_type == list: json_type = "array"
        
        param_schema["type"] = json_type
        
        # Determine if required (no default value)
        if param.default == inspect.Parameter.empty:
            parameters["required"].append(param_name)
        else:
            # Add default to description or schema? 
            # OpenAI doesn't support 'default' in schema strictly mostly, but we can hint it.
            pass

        parameters["properties"][param_name] = param_schema

    schema = {
        "name": method_path.split(".")[-1],
        "description": description,
        "parameters": parameters
    }
    
    return schema
