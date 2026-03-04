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
    return conv


def get_history(conversation, limit=None, include_tool_messages=True):
    """Load last N messages as LLM-compatible message dicts.

    When include_tool_messages=False, tool_call and tool_result messages are
    filtered out — useful for keeping context concise on long conversations.
    The most recent tool exchange (last 4 messages) is always included so the
    model knows the latest tool state.
    """
    if not conversation.messages:
        return []

    if limit is None:
        try:
            settings = frappe.get_single("OwlAI Settings")
            limit = getattr(settings, "context_message_limit", None) or 20
        except Exception:
            limit = 20

    all_msgs = conversation.messages

    # Auto-filter tool messages when conversation is long (>2x limit)
    if len(all_msgs) > limit * 2 and include_tool_messages:
        include_tool_messages = False

    recent = all_msgs[-limit:] if len(all_msgs) > limit else all_msgs

    history = []
    for i, msg in enumerate(recent):
        # Filter tool messages if requested, but keep the last 4 (recent tool exchange)
        if not include_tool_messages and msg.message_type in ("tool_call", "tool_result"):
            if i < len(recent) - 4:
                continue

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


def save_message(conversation, role, content, message_type="text", action_data=None,
                  tool_call_id=None, tool_name=None, model_used=None, tokens_used=None,
                  response_time_ms=None):
    """Append a message to the conversation's child table."""
    if tool_call_id:
        action_data = action_data or {}
        action_data["tool_call_id"] = tool_call_id
        if tool_name:
            action_data["tool_name"] = tool_name

    row = {
        "role": role,
        "content": (content or "")[:100000],
        "message_type": message_type,
        "action_data": json.dumps(action_data, default=str) if action_data else None,
    }
    if tool_call_id:
        row["tool_call_id"] = tool_call_id
    if tool_name:
        row["tool_name"] = tool_name
    if model_used:
        row["model_used"] = model_used
    if tokens_used:
        row["tokens_used"] = tokens_used
    if response_time_ms:
        row["response_time_ms"] = response_time_ms

    conversation.append("messages", row)
    conversation.message_count = len(conversation.messages)
    conversation.save(ignore_permissions=True)


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
