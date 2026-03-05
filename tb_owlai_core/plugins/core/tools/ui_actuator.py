from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import frappe
from tb_owlai_core.plugins.base import BaseTool


VALID_ACTION_TYPES = {"navigate", "new_doc", "set_value", "save", "reload", "show_alert"}


class UIActionStep(BaseModel):
    type: str = Field(..., description="Action type: navigate, new_doc, set_value, save, reload, show_alert")
    doctype: Optional[str] = Field(None, description="DocType for navigate/new_doc actions")
    docname: Optional[str] = Field(None, description="Document name for navigate action")
    view: Optional[str] = Field(None, description="View type for navigate: List, Form, Report")
    fieldname: Optional[str] = Field(None, description="Field name for set_value action")
    value: Optional[Any] = Field(None, description="Value for set_value action")
    message: Optional[str] = Field(None, description="Message for show_alert action")
    indicator: Optional[str] = Field(None, description="Indicator color for show_alert: green, blue, orange, red")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters for navigate list view")
    description: Optional[str] = Field(None, description="Human-readable description of this step")


class UIActuatorSchema(BaseModel):
    actions: List[Dict[str, Any]] = Field(
        ...,
        description=(
            "Sequence of UI actions. Each action has a 'type' and type-specific params. "
            "Types: navigate (open form/list), new_doc (create new form), "
            "set_value (fill a field), save (save current form), "
            "reload (reload form), show_alert (show notification). "
            "Example: [{\"type\": \"new_doc\", \"doctype\": \"Sales Order\"}, "
            "{\"type\": \"set_value\", \"fieldname\": \"customer\", \"value\": \"Ram Kumar\"}, "
            "{\"type\": \"save\"}]"
        )
    )


class UIActuator(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "ui_actuator"
        self.description = (
            "Execute a sequence of UI actions to visually automate the interface: "
            "navigate to forms, fill fields, save documents, show alerts. "
            "Use this when the user wants visible automation instead of silent backend operations."
        )
        self.category = "UI Automation"
        self.args_schema = UIActuatorSchema

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        actions = arguments.get("actions", [])

        if not actions:
            return {"error": "No actions provided."}

        validated_steps = []
        errors = []

        for i, step in enumerate(actions):
            action_type = step.get("type")

            if not action_type:
                errors.append(f"Step {i + 1}: missing 'type' field")
                continue

            if action_type not in VALID_ACTION_TYPES:
                errors.append(f"Step {i + 1}: unknown action type '{action_type}'. Valid: {', '.join(sorted(VALID_ACTION_TYPES))}")
                continue

            # Validate per action type
            if action_type in ("navigate", "new_doc"):
                doctype = step.get("doctype")
                if not doctype:
                    errors.append(f"Step {i + 1}: '{action_type}' requires 'doctype'")
                    continue
                if not frappe.db.exists("DocType", doctype):
                    errors.append(f"Step {i + 1}: DocType '{doctype}' does not exist")
                    continue
                if not frappe.has_permission(doctype, "read"):
                    errors.append(f"Step {i + 1}: no permission to access '{doctype}'")
                    continue

            elif action_type == "set_value":
                fieldname = step.get("fieldname")
                if not fieldname:
                    errors.append(f"Step {i + 1}: 'set_value' requires 'fieldname'")
                    continue
                # Field validation happens on the frontend (we may not know
                # which form is open when this runs server-side)

            # Build validated step with description
            validated_step = {"type": action_type}
            for key in ("doctype", "docname", "view", "fieldname", "value",
                        "message", "indicator", "filters"):
                if key in step and step[key] is not None:
                    validated_step[key] = step[key]

            # Auto-generate description if not provided
            if "description" not in step:
                validated_step["description"] = self._describe_step(validated_step)
            else:
                validated_step["description"] = step["description"]

            validated_steps.append(validated_step)

        if errors:
            return {
                "status": "Error",
                "error": "Action sequence validation failed.",
                "details": errors,
            }

        if not validated_steps:
            return {"error": "No valid actions after validation."}

        # Return as action for frontend — engine detects via result["action"]
        return {
            "action": "ui_sequence",
            "steps": validated_steps,
            "message": f"Executing {len(validated_steps)} UI action(s)...",
            "step_count": len(validated_steps),
        }

    def _describe_step(self, step):
        """Generate a human-readable description for a UI action step."""
        t = step["type"]
        if t == "navigate":
            docname = step.get("docname")
            if docname:
                return f"Open {step.get('doctype')} {docname}"
            return f"Open {step.get('doctype')} {step.get('view', 'List')}"
        elif t == "new_doc":
            return f"Create new {step.get('doctype')}"
        elif t == "set_value":
            val = step.get("value", "")
            if isinstance(val, str) and len(val) > 30:
                val = val[:30] + "..."
            return f"Set {step.get('fieldname')} = {val}"
        elif t == "save":
            return "Save document"
        elif t == "reload":
            return "Reload document"
        elif t == "show_alert":
            return step.get("message", "Show notification")
        return t
