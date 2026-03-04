"""
OwlAI API Router — All @frappe.whitelist() endpoints.
Uses the native OwlEngine (no agno/litellm/crewai dependencies).
"""

import frappe
from werkzeug.wrappers import Response
import json
import time
import traceback

from tb_owlai_core.utils.context import OwlContext
from tb_owlai_core.engine.core import OwlEngine
from tb_owlai_core.engine import conversation as conv_store

# SSE stream timeout (seconds) — prevents hung connections
SSE_STREAM_TIMEOUT = 120


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

def _check_rate_limit(user):
    """Enforce per-user rate limiting. Raises if limit exceeded."""
    try:
        settings = frappe.get_single("OwlAI Settings")
        limit = getattr(settings, "rate_limit_per_minute", 0) or 0
        if limit <= 0:
            return
    except Exception:
        return

    cache_key = f"owlai:rate:{user}"
    count = frappe.cache().get_value(cache_key) or 0

    if count >= limit:
        frappe.throw(
            f"Rate limit exceeded ({limit} requests/minute). Please wait and try again.",
            title="Rate Limit",
        )

    frappe.cache().set_value(cache_key, count + 1, expires_in_sec=60)


# ---------------------------------------------------------------------------
# Analytics logging
# ---------------------------------------------------------------------------

def _log_analytics(user, model_id, response_time, usage, status, tool_calls,
                   full_prompt, full_response, error_message=None):
    """Log execution metrics to OwlAI Analytics if enabled."""
    try:
        settings = frappe.get_single("OwlAI Settings")
        if not settings.enable_analytics:
            return

        doc = frappe.get_doc({
            "doctype": "OwlAI Analytics",
            "user": user,
            "timestamp": frappe.utils.now(),
            "status": status,
            "model": _resolve_model_link(model_id),
            "response_time": response_time,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "tool_calls": json.dumps(tool_calls, indent=2) if tool_calls else None,
            "full_prompt": full_prompt[:10000] if full_prompt else "",
            "full_response": full_response[:10000] if full_response else "",
            "error_message": error_message,
        })
        doc.insert(ignore_permissions=True)
    except Exception as e:
        frappe.logger("owlai").error(f"Analytics logging failed: {e}")


def _resolve_model_link(model_identifier):
    """Resolve a model name to a valid OwlAI Model link, or None."""
    if not model_identifier:
        return None
    if frappe.db.exists("OwlAI Model", model_identifier):
        return model_identifier
    search_name = model_identifier.split("/", 1)[-1] if "/" in model_identifier else model_identifier
    return frappe.db.get_value("OwlAI Model", {"model_name": search_name}, "name")


# ---------------------------------------------------------------------------
# Chat Endpoints
# ---------------------------------------------------------------------------

def _parse_context(route, context_str):
    """Parse context from frontend into OwlContext."""
    context_data = {}
    if context_str:
        try:
            context_data = json.loads(context_str)
        except (json.JSONDecodeError, TypeError):
            pass

    current_route = route or context_data.get("route")

    return OwlContext(
        route=current_route,
        doctype=context_data.get("doctype"),
        docname=context_data.get("docname"),
        form_data=context_data.get("form_data"),
        selected_items=context_data.get("selected_items"),
    )


@frappe.whitelist()
def handle_stream_input(route=None, text=None, conversation_id=None, context=None, mode=None):
    """Streaming chat handler (SSE). Primary endpoint for the frontend."""
    user = frappe.session.user
    _check_rate_limit(user)

    try:
        agent_context = _parse_context(route, context)

        engine = OwlEngine(
            user=user,
            conversation_id=conversation_id,
        )

        # Update route on conversation if not set
        if route and not engine.conversation.context_route:
            engine.conversation.context_route = route
            engine.conversation.save(ignore_permissions=True)

        def generate():
            # Clear any queued server messages (e.g. from get_password warnings)
            # that would cause Frappe to abort the streaming response
            if hasattr(frappe.local, "message_log"):
                frappe.local.message_log = []

            full_response_text = ""
            start_time = time.time()
            status = "Success"
            error_message = None

            try:
                for event in engine.run_stream(text, context=agent_context):
                    # Check stream timeout
                    if time.time() - start_time > SSE_STREAM_TIMEOUT:
                        timeout_msg = f"\n\n[Response timed out after {SSE_STREAM_TIMEOUT}s]"
                        yield f"data: {json.dumps({'token': timeout_msg})}\n\n"
                        break
                    yield event

                    # Track full response for analytics
                    if "token" in event and "data:" in event:
                        try:
                            payload = json.loads(event.split("data: ", 1)[1].strip())
                            if "token" in payload:
                                full_response_text += payload["token"]
                        except (json.JSONDecodeError, IndexError):
                            pass

            except Exception as e:
                status = "Error"
                error_message = str(e)
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                frappe.log_error(title="OwlAI Stream Error", message=traceback.format_exc())

            finally:
                duration = time.time() - start_time
                try:
                    model_id = engine.client.model if hasattr(engine.client, "model") else "unknown"
                    _log_analytics(
                        user=user,
                        model_id=model_id,
                        response_time=duration,
                        usage={},
                        status=status,
                        tool_calls=[],
                        full_prompt=text,
                        full_response=full_response_text,
                        error_message=error_message,
                    )
                except Exception:
                    pass

        return Response(generate(), mimetype="text/event-stream")

    except Exception as top_e:
        frappe.log_error(
            title="OwlAI Stream Fatal Error",
            message=traceback.format_exc(),
        )
        return Response(
            f"event: error\ndata: {json.dumps({'error': str(top_e)})}\n\n",
            status=200,
            mimetype="text/event-stream",
        )


@frappe.whitelist()
def handle_input_v2(route=None, text=None, conversation_id=None, context=None, mode=None):
    """Non-streaming chat handler. Returns JSON dict."""
    user = frappe.session.user
    _check_rate_limit(user)

    agent_context = _parse_context(route, context)

    try:
        engine = OwlEngine(
            user=user,
            conversation_id=conversation_id,
        )
    except Exception as e:
        frappe.log_error(title="Agent Init Error", message=traceback.format_exc())
        return {"reply": f"Failed to initialize AI Agent: {str(e)}"}

    # Update route on conversation
    if route and not engine.conversation.context_route:
        engine.conversation.context_route = route
        engine.conversation.save(ignore_permissions=True)

    start_time = time.time()
    status = "Success"
    error_message = None
    result = {}

    try:
        result = engine.run(text, context=agent_context)
        result["reply"] = _repair_links(result.get("reply", ""))
        return result

    except Exception as e:
        status = "Error"
        error_message = traceback.format_exc()
        frappe.log_error(title="OwlAI Agent Error", message=error_message)
        result = {"reply": f"An error occurred: {str(e)}"}
        return result

    finally:
        duration = time.time() - start_time
        try:
            model_id = engine.client.model if hasattr(engine.client, "model") else "unknown"
            _log_analytics(
                user=user,
                model_id=model_id,
                response_time=duration,
                usage=result.get("usage", {}),
                status=status,
                tool_calls=[],
                full_prompt=text,
                full_response=result.get("reply", ""),
                error_message=error_message,
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Conversation Management
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_conversations(limit=20, search_text=None):
    """List conversations visible to the current user."""
    user = frappe.session.user
    filters = {"status": "Active"}

    if search_text:
        filters["title"] = ["like", f"%{search_text}%"]

    return frappe.get_all(
        "OwlAI Conversation",
        filters=filters,
        or_filters=[["owner", "=", user], ["sharing_type", "=", "Public"]],
        fields=["name", "title", "modified"],
        order_by="modified desc",
        limit=limit,
    )


@frappe.whitelist()
def new_conversation():
    """Create a new empty conversation."""
    conv = conv_store.load_or_create()
    return {"conversation_id": conv.name}


@frappe.whitelist()
def delete_conversation(conversation_id):
    """Delete a conversation. Only owner or System Manager allowed."""
    if not conversation_id:
        return {"status": "error", "message": "No conversation_id provided"}

    try:
        conv = frappe.get_doc("OwlAI Conversation", conversation_id)

        # Ownership check
        if conv.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
            frappe.throw("You can only delete your own conversations", frappe.PermissionError)

        frappe.delete_doc("OwlAI Conversation", conversation_id)
        return {"status": "success"}
    except frappe.PermissionError:
        return {"status": "error", "message": "Permission denied"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def update_conversation_title(conversation_id, title):
    """Rename a conversation. Only owner or System Manager allowed."""
    if not conversation_id or not title:
        return {"status": "error", "message": "Missing parameters"}

    try:
        conv = frappe.get_doc("OwlAI Conversation", conversation_id)
        if conv.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
            frappe.throw("Permission denied", frappe.PermissionError)

        frappe.db.set_value("OwlAI Conversation", conversation_id, "title", title)
        return {"status": "success"}
    except frappe.PermissionError:
        return {"status": "error", "message": "Permission denied"}
    except Exception as e:
        frappe.log_error(title="Error updating title", message=traceback.format_exc())
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_conversation_messages(conversation_id):
    """Load all messages for a conversation."""
    if not conversation_id:
        return []

    try:
        conv = frappe.get_doc("OwlAI Conversation", conversation_id)
        if not conv.has_permission("read"):
            return []

        messages = []
        for m in conv.messages:
            try:
                action_data = json.loads(m.action_data) if m.action_data else None
            except (json.JSONDecodeError, TypeError):
                action_data = None

            messages.append({
                "role": m.role,
                "content": _repair_links(m.content),
                "message_type": m.message_type,
                "creation": m.creation,
                "idx": m.idx,
                "action_data": action_data,
            })
        return messages
    except Exception:
        return []


@frappe.whitelist()
def get_conversation_info(conversation_id):
    """Get conversation metadata."""
    if not conversation_id:
        return None

    try:
        conv = frappe.get_doc("OwlAI Conversation", conversation_id)
        if not conv.has_permission("read"):
            return None
        return {
            "name": conv.name,
            "title": conv.title,
            "status": conv.status,
            "modified": conv.modified,
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Settings (System Manager only)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def update_owlai_settings(model=None, enable_analytics=None, **kwargs):
    """Update OwlAI Settings. System Manager only."""
    frappe.only_for("System Manager")

    settings = frappe.get_single("OwlAI Settings")

    if model and frappe.db.exists("OwlAI Model", model):
        settings.default_model = model
    if enable_analytics is not None:
        settings.enable_analytics = int(enable_analytics)

    settings.save(ignore_permissions=True)
    return {"status": "success"}


@frappe.whitelist()
def clear_owlai_cache():
    """Clear the OwlAI Redis cache. System Manager only."""
    frappe.only_for("System Manager")

    from tb_owlai_core.utils.cache import OwlCache

    OwlCache.clear()
    return {"status": "success", "message": "Cache cleared."}


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@frappe.whitelist()
def health_check():
    """Validate the OwlAI stack. System Manager only."""
    frappe.only_for("System Manager")

    import os
    import requests

    result = {
        "ollama": False,
        "ollama_models": [],
        "default_agent": None,
        "tools_count": 0,
        "providers": [],
        "models": [],
    }

    # Check Ollama
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        resp = requests.get(f"{ollama_host}/api/tags", timeout=2)
        if resp.ok:
            result["ollama"] = True
            result["ollama_models"] = [
                m["name"] for m in resp.json().get("models", [])
            ]
    except Exception:
        pass

    # Check config
    try:
        settings = frappe.get_single("OwlAI Settings")
        result["default_agent"] = settings.default_agent
    except Exception:
        pass

    result["tools_count"] = frappe.db.count("OwlAI Tool")
    result["providers"] = frappe.get_all(
        "OwlAI Provider", fields=["provider_name", "api_base", "is_default"]
    )
    result["models"] = frappe.get_all(
        "OwlAI Model", fields=["model_name", "provider", "supports_function_calling"]
    )

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repair_links(text):
    """Fix case-sensitivity in Frappe document links generated by the LLM."""
    import re

    if not text:
        return text

    links = re.findall(r"(/app/([a-z0-9\-]+)/([a-zA-Z0-9\-\%_\.]+))", text)

    for full_match, slug, original_id in links:
        doctype = slug.replace("-", " ").title()
        if not frappe.db.exists("DocType", doctype):
            continue
        if frappe.db.exists(doctype, original_id):
            continue
        actual_name = frappe.db.get_value(
            doctype, {"name": ["like", original_id]}, "name"
        )
        if actual_name and actual_name != original_id:
            text = text.replace(full_match, f"/app/{slug}/{actual_name}")

    return text
