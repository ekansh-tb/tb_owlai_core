from tb_owlai_core.plugins.base import BaseTool

class NavigateTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="navigate",
            description="Navigate the user to a specific DocType list or page in the Frappe Desk. Use this when the user asks to 'Show' or 'Go to' a list or page.",
            category="Navigation",
            inputSchema={
                "type": "object",
                "properties": {
                    "doctype": {
                        "type": "string",
                        "description": "The DocType to navigate to (e.g. Sales Order, Task, Item)."
                    },
                    "view": {
                        "type": "string",
                        "description": "The view type (List, Report, Dashboard, Kanban, Tree). Default is List.",
                        "enum": ["List", "Report", "Dashboard", "Kanban", "Tree"]
                    }
                },
                "required": ["doctype"]
            }
        )

    def execute(self, **kwargs):
        # This tool is primarily a signal for the client-side router.
        # But if executed, we returned structured info.
        return {
            "status": "navigating",
            "message": f"Navigating to {kwargs.get('doctype')}",
            "doctype": kwargs.get("doctype"),
            "view": kwargs.get("view", "List")
        }
