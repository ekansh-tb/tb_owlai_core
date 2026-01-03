from typing import Any, Dict
import frappe
import frappe.desk.query_report
from tb_owlai_core.plugins.base import BaseTool

class GenerateReport(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "generate_report"
        self.description = "Run a Frappe report."
        self.category = "Reporting"
        self.inputSchema = {
            "type": "object",
            "properties": {
                "report_name": {"type": "string"},
                "filters": {"type": "object"}
            },
            "required": ["report_name"]
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        report_name = arguments.get("report_name")
        filters = arguments.get("filters", {})

        try:
            # Check if report exists
            if not frappe.db.exists("Report", report_name):
                 return {"error": f"Report '{report_name}' not found."}

            # Run Report
            result = frappe.desk.query_report.run(report_name, filters=filters)
            
            columns = result.get("columns", [])
            data = result.get("result", [])
            
            # Return summarized data
            # Limit rows
            return {
                "report": report_name,
                "columns": [c.get("label") for c in columns] if columns else [],
                "data": data[:20], # Limit to 20 rows
                "message": f"Showing first 20 rows of {len(data)} total result(s)."
            }

        except Exception as e:
            return {"error": str(e)}
