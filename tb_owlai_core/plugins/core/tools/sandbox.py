from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import frappe
from frappe.utils.safe_exec import safe_exec
from tb_owlai_core.plugins.base import BaseTool

class SandboxSchema(BaseModel):
    code: str = Field(..., description="Python code to execute. Available context: 'frappe'. Returns value of last expression or printed output.")

class Sandbox(BaseTool):
    args_schema: Optional[type] = SandboxSchema

    def __init__(self):
        super().__init__()
        self.name = "sandbox"
        self.description = "Execute safe, read-only Python code for complex aggregations. Use this for calculations that standard DB queries cannot handle easily."
        self.category = "Advanced"
        self.args_schema = SandboxSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        code = arguments.get("code")
        
        try:
            # Prepare safe context
            # safe_exec by default provides a restricted frappe key
            result = safe_exec(code)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
