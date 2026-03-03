"""
Conversation storage — thin wrapper around OwlAI Conversation DocType.
Replaces the 300-line agno FrappeStorage adapter with ~60 lines.
"""

import frappe
import json


def load_or_create(conversation_id=None, user=None):
    """Load an existing conversation (with permission check) or create a new one."""
    user = user or frappe.session.user

    if conversation_id:
        try:
            conv = frappe.get_doc("OwlAI Conversation", conversation_id)
            if not conv.has_permission("read"):
                frappe.throw(
                    "No permission to access this conversation",
                    frappe.PermissionError,
                )
            return conv
        except frappe.DoesNotExistError:
            pass

    # Create new conversation
    conv = frappe.get_doc({
        "doctype": "OwlAI Conversation",
        "owner": user,
        "sharing_type": "Private",
        "status": "Active",
    })
    conv.insert(ignore_permissions=True)
    conv.session_id = conv.name
    conv.save(ignore_permissions=True)
    frappe.db.commit()
    return conv


def get_history(conversation, limit=None):
    """Load last N messages as LLM-compatible message dicts."""
    if not conversation.messages:
        return []

    if limit is None:
        try:
            settings = frappe.get_single("OwlAI Settings")
            limit = getattr(settings, "context_message_limit", None) or 20
        except Exception:
            limit = 20

    recent = conversation.messages[-limit:] if len(conversation.messages) > limit else conversation.messages

    history = []
    for msg in recent:
        entry = {"role": msg.role, "content": msg.content or ""}

        # Restore tool_calls for assistant messages
        if msg.role == "assistant" and msg.action_data:
            try:
                action = json.loads(msg.action_data)
                if isinstance(action, dict) and action.get("tool_calls"):
                    entry["tool_calls"] = action["tool_calls"]
            except (json.JSONDecodeError, TypeError):
                pass

        # Restore tool_call_id for tool result messages
        if msg.role == "tool" and msg.action_data:
            try:
                action = json.loads(msg.action_data)
                if isinstance(action, dict) and action.get("tool_call_id"):
                    entry["tool_call_id"] = action["tool_call_id"]
            except (json.JSONDecodeError, TypeError):
                pass

        history.append(entry)

    return history


def save_message(conversation, role, content, message_type="text", action_data=None):
    """Append a message to the conversation's child table."""
    conversation.append("messages", {
        "role": role,
        "content": (content or "")[:100000],
        "message_type": message_type,
        "action_data": json.dumps(action_data, default=str) if action_data else None,
    })
    conversation.message_count = len(conversation.messages)
    conversation.save(ignore_permissions=True)
    frappe.db.commit()


def update_title(conversation, text):
    """Auto-generate conversation title from first user message."""
    if not text:
        return

    should_update = (
        not conversation.title
        or conversation.title == conversation.name
        or conversation.title.startswith("Conversation ")
        or "OWL-CONV-" in (conversation.title or "")
        or conversation.title == "New Conversation"
    )

    if not should_update:
        return

    title = text.strip().split("\n")[0]
    title = title[:60] + "..." if len(title) > 60 else title

    conversation.title = title
    conversation.save(ignore_permissions=True)
    frappe.db.commit()
