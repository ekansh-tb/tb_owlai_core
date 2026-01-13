import frappe
from frappe.model.document import Document
from tb_owlai_core.utils.tool_serializer import get_function_schema
import json

class OwlAITool(Document):
    def validate(self):
        if self.type == "Python Method" and self.method_path:
            # Generate schema if missing or if explicitly requested (we could add a flag later)
            # For now, let's generate if empty.
            if not self.args_schema:
                try:
                    schema = get_function_schema(self.method_path)
                    # We might want to override the name in the schema with the actual tool name
                    schema["name"] = self.tool_name
                    self.args_schema = json.dumps(schema, indent=4)
                except Exception as e:
                    frappe.msgprint(f"Warning: Could not auto-generate schema: {e}")

