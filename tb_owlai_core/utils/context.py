import frappe
import json

class OwlContext:
    def __init__(self, route=None, doctype=None, docname=None, form_data=None, selected_items=None):
        self.route = route
        self.form_data = form_data or {}
        self.selected_items = selected_items or []
        self.doctype = doctype
        self.docname = docname
        
        if not self.doctype or not self.docname:
            self._parse_route(route)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def _parse_route(self, route):
        """
        Extracts DocType and DocName from the current route.
        Supported formats:
        - Form/ToDo/Task-001
        - List/ToDo/List
        - app/todo (URL style)
        """
        if not route: return
        
        parts = route.strip("/").split("/")
        
        # Handle /app/ prefix if present
        if parts[0] == "app":
            parts.pop(0)
            
        if not parts: return

        # Case 1: Standard Desk Route (Form/DocType/Name or List/DocType/...)
        if parts[0] in ["Form", "List"]:
            if len(parts) >= 2:
                self.doctype = parts[1]
                if parts[0] == "Form" and len(parts) >= 3:
                     self.docname = parts[2]
            return

        # Case 2: URL slug style (todo, user, etc.)
        doctype_slug = parts[0]
        if doctype_slug in ["query-report", "dashboard-view", "kanban-view"]:
             return 
             
        # Try to find DocType
        # 1. Direct Name Match
        if frappe.db.exists("DocType", doctype_slug):
            self.doctype = doctype_slug
        else:
            # 2. Slug to Title
            possible_name = doctype_slug.replace("-", " ").title()
            if frappe.db.exists("DocType", possible_name):
                 self.doctype = possible_name
            else:
                # 3. DB Search
                try:
                     dt = frappe.db.get_value("DocType", {"name": ["like", doctype_slug]}, "name")
                     if dt: self.doctype = dt
                except: pass
        
        # Extract DocName if available (doctype/docname)
        if self.doctype and len(parts) >= 2:
            self.docname = parts[1]

    def get_schema_context_string(self):
        """
        Returns a formatted string containing the schema of the current DocType.
        """
        if not self.doctype:
            return ""
            
        try:
            meta = frappe.get_meta(self.doctype)
            # Basic Info
            schema_text = f"DocType: {self.doctype}\n"
            schema_text += f"Description: {meta.description or 'No description'}\n"
            schema_text += f"Is Submittable: {'Yes' if meta.is_submittable else 'No'}\n"
            
            # Fields
            schema_text += "Fields (First 50):\n"
            fields = []
            for df in meta.fields:
                 if df.fieldtype not in ["Section Break", "Column Break", "Tab Break", "HTML", "Image", "Fold"] and not df.hidden:
                     field_info = f"- {df.fieldname} ({df.fieldtype}): {df.label}"
                     if df.options and df.fieldtype in ["Link", "Select"]:
                          field_info += f" [Options: {df.options}]"
                     if df.reqd:
                          field_info += " [Required]"
                     fields.append(field_info)
            
            schema_text += "\n".join(fields[:50])
            
            return f"""
\n---
CONTEXT: USER IS CURRENTLY VIEWING DOCTYPE '{self.doctype}'.
SCHEMA INFORMATION:
{schema_text}
---
"""
        except Exception as e:
            # Don't fail the whole request if schema fetch fails
            frappe.log_error(f"Schema fetch error for {self.doctype}: {e}")
            return ""

    def get_data_context_string(self):
        """
        Returns a formatted string containing current form data or selection.
        """
        context_str = ""
        
        if self.form_data:
            context_str += f"\n--- CURRENT FORM DATA ({self.doctype}) ---\n"
            context_str += json.dumps(self.form_data, indent=2)
            context_str += "\n-------------------------------------\n"
            
        if self.selected_items:
            context_str += f"\n--- SELECTED ITEMS ({len(self.selected_items)}) ---\n"
            context_str += json.dumps(self.selected_items, indent=2)
            context_str += "\n-------------------------------------\n"
            
        return context_str

    def get_full_context_string(self):
        """
        Combines Route, Schema, and Data context.
        """
        full_context = f"Current Route: {self.route}\n"
        if self.docname:
            full_context += f"Current Document: {self.docname}\n"
            
        full_context += self.get_schema_context_string()
        full_context += self.get_data_context_string()
        return full_context
