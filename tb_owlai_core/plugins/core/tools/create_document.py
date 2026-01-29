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
        # Handle 'properties' as alias for 'data' for backward compatibility/Anekantvada
        if not data and "properties" in arguments:
            data = arguments.get("properties", {})
            
        validate_only = arguments.get("validate_only", False)

        if not frappe.db.exists("DocType", doctype):
            return {"error": f"DocType '{doctype}' does not exist."}

        try:
            meta = frappe.get_meta(doctype)
            valid_fields = {f.fieldname for f in meta.fields}
            valid_fields.update(["name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "doctype", "flags", "_user_tags", "_comments", "_assign", "_liked_by"])
            
            # --- SMART FIELD MAPPING ---
            field_map = {}
            for f in meta.fields:
                if f.label:
                    field_map[f.label.lower()] = f.fieldname
                field_map[f.fieldname] = f.fieldname

            # Process data and remap keys
            new_data = {}
            for key, value in data.items():
                lower_key = key.lower()
                clean_key = lower_key.replace("_", " ").strip()
                if key in valid_fields:
                    new_data[key] = value
                elif lower_key in field_map:
                    new_data[field_map[lower_key]] = value
                elif clean_key in field_map:
                    new_data[field_map[clean_key]] = value
                else:
                    new_data[key] = value
            data = new_data
            
            # Use frappe.new_doc to handle defaults and then check mandatory
            temp_doc = frappe.new_doc(doctype)
            for k, v in data.items():
                if hasattr(temp_doc, k):
                     if isinstance(v, list) and meta.get_field(k) and meta.get_field(k).fieldtype == 'Table':
                         temp_doc.set(k, v)
                     else:
                         setattr(temp_doc, k, v)
            
            missing_mandatory = []
            for f in meta.fields:
                if f.reqd:
                    val = getattr(temp_doc, f.fieldname, None)
                    # For Tables, check if list is empty
                    is_empty = False
                    if f.fieldtype == 'Table':
                        if not val or len(val) == 0:
                            is_empty = True
                    elif val is None or val == "":
                        is_empty = True
                        
                    if is_empty:
                        missing_mandatory.append({
                            "fieldname": f.fieldname,
                            "label": f.label,
                            "fieldtype": f.fieldtype,
                            "options": f.options
                        })

            if missing_mandatory and not validate_only:
                return {
                    "status": "Incomplete",
                    "error": f"Missing mandatory fields for {doctype}.",
                    "missing_fields": missing_mandatory,
                    "message": f"To create a {doctype}, I need values for: " + 
                               ", ".join([f"{f['label']}" for f in missing_mandatory])
                }

            invalid_fields = [k for k in data.keys() if k not in valid_fields and not k.startswith("_")]
            if invalid_fields:
                return {
                    "status": "Error",
                    "error": f"Invalid fields for {doctype}: {', '.join(invalid_fields)}.",
                    "valid_fields_hint": list(valid_fields)[:20] # Provide some valid ones
                }

            # Map 'title' to 'description' hack
            if "title" in data and not meta.has_field("title") and meta.has_field("description"):
                if not data.get("description"):
                    data["description"] = data.pop("title")

        except Exception as e:
            frappe.log_error(f"Metadata Fetch Error: {str(e)}")
            # Fallback to direct creation if meta fails (rare)

        # Permission Check
        if not frappe.has_permission(doctype, "create"):
             return {"error": f"You do not have permission to create '{doctype}'."}

        try:
            doc = frappe.new_doc(doctype)
            
            # Populate fields
            for key, value in data.items():
                if isinstance(value, list) and meta.get_field(key) and meta.get_field(key).fieldtype == 'Table':
                    doc.set(key, []) # Clear defaults if we have data
                    for row in value:
                        doc.append(key, row)
                else:
                    if hasattr(doc, key):
                        setattr(doc, key, value)
            
            if "name" in data and not doc.name:
                doc.name = data["name"]

            if validate_only:
                doc.validate()
                return {"status": "valid", "message": "Validation successful"}

            doc.insert(ignore_permissions=True) 

            if submit and doc.docstatus == 0 and doc.meta.is_submittable:
                if frappe.has_permission(doctype, "submit", doc=doc.name):
                    doc.submit()
                else:
                    return {
                        "name": doc.name, 
                        "warning": "Document created but submit permission denied."
                    }

            frappe.db.commit()
            
            slug = doctype.lower().replace(" ", "-")
            result = {
                "name": doc.name,
                "doctype": doc.doctype,
                "url": f"/app/{slug}/{doc.name}",
                "status": "Submitted" if doc.docstatus == 1 else "Saved",
                "message": f"Created {doctype}: {doc.name}",
                "action": "navigate",
                "view": "Form",
                "docname": doc.name
            }

            if not hasattr(frappe.local, 'owlai_actions'):
                frappe.local.owlai_actions = []
            frappe.local.owlai_actions.append(result)

            return result

        except frappe.MandatoryError as e:
            missing = e.args[0] if e.args and isinstance(e.args[0], list) else [str(e)]
            return {
                "status": "Incomplete",
                "error": f"Missing mandatory fields: {', '.join(missing)}",
                "message": "Please provide values for these mandatory fields."
            }
        except Exception as e:
            frappe.log_error(f"Create Document Error: {str(e)}")
            return {"status": "Error", "error": str(e)}
