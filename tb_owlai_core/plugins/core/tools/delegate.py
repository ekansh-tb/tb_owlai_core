from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
import frappe
from tb_owlai_core.plugins.base import BaseTool

class DelegateSchema(BaseModel):
    agent_id: str = Field(..., description="The ID (name) of the Agent to delegate to, e.g., 'Owl Assistant' or 'frappe_coder'.")
    task: str = Field(..., description="The specific task or instruction for the delegate agent.")
    context: Optional[str] = Field(None, description="Optional additional context or data.")

class DelegateTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "delegate_task"
        self.description = "Delegate a sub-task to another specialized Agent. Use this to leverage domain-specific experts."
        self.category = "Orchestration"
        self.args_schema = DelegateSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        agent_id = arguments.get("agent_id")
        task = arguments.get("task")
        context = arguments.get("context", "")
        
        if not agent_id or not task:
            return {"error": "agent_id and task are required."}

        # Check if agent exists
        if not frappe.db.exists("OwlAI Agent", agent_id):
             # Try fuzzy matching or list available agents
             agents = frappe.get_all("OwlAI Agent", pluck="name")
             return {"error": f"Agent '{agent_id}' not found. Available: {', '.join(agents)}"}

        try:
            # We need to invoke the agent safely.
            # Using frappe.call to run the agent runner logic?
            # Or instantiating OwlAgent directly.
            # Direct instantiation is better for internal delegation to avoid HTTP overhead.
            
            from tb_owlai_core.owlai_core.agent import OwlAgent
            
            # Create a localized runner
            # We should probably pass the current user if possible, or use Administrator
            user = frappe.session.user
            
            runner = OwlAgent(user=user, agent_id=agent_id)
            
            # The 'task' is the input message
            full_prompt = f"{task}\n\nContext: {context}" if context else task
            
            response = runner.run(user_message=full_prompt)
            
            return {
                "delegate_reply": response.get("reply"),
                "status": "success"
            }
            
        except Exception as e:
            frappe.log_error(f"Delegate Error to {agent_id}: {e}")
            return {"error": f"Delegation failed: {str(e)}"}
