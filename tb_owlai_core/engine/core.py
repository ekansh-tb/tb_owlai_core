"""
OwlEngine — The Frappe-native AI agent loop.
Zero framework dependencies. ~250 lines replacing ~1500 lines of agno wrappers.

Responsibility:
1. Build context-aware system prompt from user's actual Frappe environment
2. Convert plugin tools to OpenAI function-calling schema
3. Run the tool-calling loop (LLM -> tool -> LLM -> ... -> text)
4. Stream tokens back via SSE
5. Persist messages to OwlAI Conversation
"""

import frappe
import json
import time
from tb_owlai_core.engine.llm import get_client
from tb_owlai_core.engine import conversation as conv_store
from tb_owlai_core.utils.context import OwlContext
from tb_owlai_core.utils.plugin_manager import PluginManager

logger = frappe.logger("owlai.engine")


class OwlEngine:
    """Frappe-native AI agent. Sees what the user sees, does what the user can do."""

    def __init__(self, user=None, conversation_id=None, agent_name=None):
        self.user = user or frappe.session.user
        self.conversation = conv_store.load_or_create(conversation_id, self.user)
        self.plugin_manager = PluginManager()
        self.max_tool_rounds = 5

        # Load agent config
        self._agent_doc = self._load_agent(agent_name)

        # Initialize LLM client
        model_doc_name = self._agent_doc.model if self._agent_doc else None
        self.client = get_client(model_doc_name)

    def _load_agent(self, agent_name=None):
        """Load agent configuration from OwlAI Agent DocType."""
        try:
            settings = frappe.get_single("OwlAI Settings")
            name = agent_name or settings.default_agent
            self.max_tool_rounds = getattr(settings, "max_agent_loops", 5) or 5
        except Exception:
            name = agent_name

        if name and frappe.db.exists("OwlAI Agent", name):
            doc = frappe.get_doc("OwlAI Agent", name)
            # Enforce role restriction
            if doc.role and doc.role not in frappe.get_roles():
                logger.warning(
                    f"User {self.user} denied access to agent {name} (requires role {doc.role})"
                )
                return None
            return doc
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, message, context=None):
        """Non-streaming agent execution. Returns dict."""
        context = context or OwlContext()

        # Save user message
        conv_store.save_message(self.conversation, "user", message)
        conv_store.update_title(self.conversation, message)

        # Build LLM inputs
        messages = self._build_messages(message, context)
        tools = self._select_tools(message)
        actions = []
        usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # Agent loop: LLM -> tool calls -> LLM -> ... -> text
        response = None
        for _round in range(self.max_tool_rounds):
            response = self.client.chat(messages, tools=tools)
            _accumulate_usage(usage_total, response.usage)

            if not response.has_tool_calls:
                break

            # Append assistant message with tool_calls
            messages.append(
                self.client.format_assistant_tool_call_message(
                    response.content, response.tool_calls
                )
            )

            # Persist assistant tool_call message
            conv_store.save_message(
                self.conversation, "assistant", response.content,
                message_type="tool_call",
                action_data={"tool_calls": [
                    {"id": tc["id"], "name": tc["name"], "arguments": tc["arguments"]}
                    for tc in response.tool_calls
                ]}
            )

            # Execute each tool, append results
            for tc in response.tool_calls:
                result_str, action = self._execute_tool(tc["name"], tc["arguments"])
                if action:
                    actions.append(action)
                messages.append(
                    self.client.format_tool_result_message(tc["id"], result_str)
                )
                # Persist tool result message
                conv_store.save_message(
                    self.conversation, "tool", result_str,
                    message_type="tool_result",
                    tool_call_id=tc["id"],
                    tool_name=tc["name"]
                )

        reply = response.content if response else ""

        # Collect side-channel actions (navigate, reload, etc.)
        actions.extend(self._drain_side_channel_actions())

        # Format actions for frontend
        action_data = _format_actions(actions) if actions else None

        # Save assistant response
        conv_store.save_message(
            self.conversation,
            "assistant",
            reply,
            message_type="action" if actions else "text",
            action_data={"actions": action_data} if action_data else None,
        )

        return {
            "reply": reply,
            "action_data": action_data,
            "conversation_id": self.conversation.name,
            "usage": usage_total,
        }

    def run_stream(self, message, context=None):
        """Streaming agent execution. Yields SSE-formatted strings."""
        context = context or OwlContext()

        # Save user message
        conv_store.save_message(self.conversation, "user", message)
        conv_store.update_title(self.conversation, message)

        # Build LLM inputs
        messages = self._build_messages(message, context)
        tools = self._select_tools(message)
        actions = []
        full_response = ""
        usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # Yield SSE start event
        model_name = getattr(self.client, 'model', 'unknown')
        yield f"event: start\ndata: {json.dumps({'conversation_id': self.conversation.name, 'model': model_name})}\n\n"

        try:
            for _round in range(self.max_tool_rounds + 1):
                content_buffer = ""
                tool_calls = []

                try:
                    stream_iter = self.client.chat_stream(messages, tools=tools)
                except Exception as init_err:
                    yield f"data: {json.dumps({'token': f'[Stream init error: {init_err}]'})}\n\n"
                    break

                for chunk in stream_iter:
                    # Stream text tokens to the client
                    if chunk.get("content"):
                        content_buffer += chunk["content"]
                        yield f"data: {json.dumps({'token': chunk['content']})}\n\n"

                    if chunk.get("done"):
                        tool_calls = chunk.get("tool_calls", [])
                        _accumulate_usage(usage_total, chunk.get("usage", {}))

                if tool_calls:
                    # Tool-calling round — execute and loop
                    messages.append(
                        self.client.format_assistant_tool_call_message(
                            content_buffer, tool_calls
                        )
                    )

                    # Persist assistant tool_call message
                    conv_store.save_message(
                        self.conversation, "assistant", content_buffer,
                        message_type="tool_call",
                        action_data={"tool_calls": [
                            {"id": tc["id"], "name": tc["name"], "arguments": tc["arguments"]}
                            for tc in tool_calls
                        ]}
                    )

                    for tc in tool_calls:
                        result_str, action = self._execute_tool(
                            tc["name"], tc["arguments"]
                        )
                        if action:
                            actions.append(action)
                            yield f"data: {json.dumps({'action_data': [{'name': action.get('action', 'navigate'), 'parameters': action}]}, default=str)}\n\n"
                        messages.append(
                            self.client.format_tool_result_message(
                                tc["id"], result_str
                            )
                        )
                        # Persist tool result message
                        conv_store.save_message(
                            self.conversation, "tool", result_str,
                            message_type="tool_result",
                            tool_call_id=tc["id"],
                            tool_name=tc["name"]
                        )
                else:
                    # Final text response — already streamed
                    full_response = content_buffer
                    break

            # Drain side-channel actions
            for action in self._drain_side_channel_actions():
                actions.append(action)
                yield f"data: {json.dumps({'action_data': [{'name': action.get('action', 'navigate'), 'parameters': action}]}, default=str)}\n\n"

        except Exception as e:
            error_msg = f"\n\n**Error:** {str(e)}"
            yield f"data: {json.dumps({'token': error_msg})}\n\n"
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            frappe.log_error(title="OwlAI Stream Error", message=str(e))
            full_response = error_msg

        finally:
            # Persist assistant response
            try:
                action_data = _format_actions(actions) if actions else None
                conv_store.save_message(
                    self.conversation,
                    "assistant",
                    full_response,
                    message_type="action" if actions else "text",
                    action_data={"actions": action_data} if action_data else None,
                )
                frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"Failed to save assistant response: {e}")

            yield "event: end\ndata: [DONE]\n\n"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_messages(self, user_message, context):
        """Assemble the full message list for the LLM.

        Note: The current user message is already saved to the conversation
        before this method is called, so get_history() already includes it.
        We do NOT append it again to avoid duplication.
        """
        messages = [{"role": "system", "content": self._build_system_prompt(context, user_message)}]
        messages.extend(conv_store.get_history(self.conversation))
        return messages

    def _build_system_prompt(self, context, user_message=None):
        """Dynamic system prompt that adapts to ANY Frappe site. Zero hardcoded DocTypes.

        Uses multi-layer context from bench introspection:
        1. Business domain context (from Redis cache)
        2. User context (roles, company, defaults)
        3. Viewport context (current route, schema, form data)
        4. Knowledge context (RAG results for the query)
        5. Tool guidance (enabled tools with hints)
        """
        site = frappe.local.site

        # Agent's custom system prompt (strip HTML from rich-text editor)
        custom_prompt = ""
        if self._agent_doc and self._agent_doc.system_prompt:
            raw = self._agent_doc.system_prompt
            if "<div" in raw or "<p>" in raw:
                from frappe.utils import strip_html
                raw = strip_html(raw)
            custom_prompt = f"\n{raw}"

        # Layer 1: Business domain context (cached, ~0ms)
        domain_ctx = context.get_domain_context() if context else ""

        # Layer 2: User context
        user_ctx = context.get_user_context() if context else ""

        # Layer 3: Viewport context (route, schema, form data)
        viewport = context.get_full_context_string() if context else ""

        # Layer 4: Knowledge context (RAG search)
        knowledge_ctx = ""
        if user_message and context:
            knowledge_ctx = context.get_knowledge_context(user_message)

        # Layer 5: Tool usage guidance
        tool_guidance = self._build_tool_guidance()

        # Token budget: keep total under ~1500 tokens
        # domain=200, user=100, viewport=500, knowledge=300, tools=200
        if len(domain_ctx) > 800:
            domain_ctx = domain_ctx[:800]
        if len(viewport) > 2000:
            viewport = viewport[:2000]
        if len(knowledge_ctx) > 1200:
            knowledge_ctx = knowledge_ctx[:1200]

        return f"""You are OwlAI, an intelligent Frappe ERP assistant for site: {site}.
You MUST call tools to answer questions. Do NOT describe tool usage in text — actually invoke them.
When asked to count, use list tool with limit_page_length=0. For navigation, use navigate tool.{custom_prompt}{domain_ctx}{user_ctx}{tool_guidance}
{viewport}{knowledge_ctx}"""

    def _build_tool_guidance(self):
        """Generate concise tool guidance from the agent's enabled tools only."""
        # Only list tools that are actually enabled for this agent
        enabled_tools = self._get_enabled_tool_names()
        if not enabled_tools:
            return ""

        hints = {
            "list_documents": "List or count records. Use limit_page_length=0 for counts.",
            "navigate": "Open a DocType list or form view.",
            "get_document": "Fetch a single document by name.",
            "create_document": "Create a new document. Check get_doctype_info first.",
            "search_documents": "Full-text search across DocTypes.",
            "get_doctype_info": "Get field schema for a DocType.",
            "update_document": "Update fields on an existing document.",
            "delete_document": "Delete a document by name.",
        }

        lines = ["\nAvailable tools:"]
        for name in enabled_tools:
            hint = hints.get(name, "")
            lines.append(f"- {name}: {hint}" if hint else f"- {name}")

        return "\n".join(lines)

    def _get_enabled_tool_names(self):
        """Return list of tool names enabled for this agent."""
        if self._agent_doc and self._agent_doc.tools:
            return [t.tool for t in self._agent_doc.tools if t.enabled]
        return list(self.plugin_manager.tools.keys())

    # Max tools to send per request — local 7B models degrade above 3-4 tools
    MAX_TOOLS_PER_REQUEST = 4

    def _select_tools(self, user_message):
        """Select the most relevant tools for the user's message.

        Local models (7B) can only reliably handle 3-4 tools at once.
        Uses: 1) DocType detection from bench introspection, 2) intent keywords,
        3) dynamic tool matching for detected DocTypes.
        """
        all_schemas = self._get_tool_schemas()
        if len(all_schemas) <= self.MAX_TOOLS_PER_REQUEST:
            return all_schemas

        msg = user_message.lower()

        # --- Phase 1: Detect DocTypes in the message ---
        detected_doctypes = []
        try:
            from tb_owlai_core.intelligence.bench_introspector import detect_doctypes_in_text
            detected_doctypes = detect_doctypes_in_text(user_message)
        except Exception:
            pass

        # --- Phase 2: Check for dynamic tools matching detected DocTypes ---
        dynamic_schemas = []
        if detected_doctypes:
            try:
                from tb_owlai_core.intelligence.tool_factory import get_relevant_dynamic_tools
                dynamic_tools = get_relevant_dynamic_tools(user_message, max_tools=2)
                for dt in dynamic_tools:
                    dynamic_schemas.append({
                        "type": "function",
                        "function": {
                            "name": dt["name"],
                            "description": dt["description"],
                            "parameters": dt["inputSchema"],
                        }
                    })
            except Exception:
                pass

        # --- Phase 3: Intent-based scoring for static tools ---
        intent_tools = {
            "navigate": ["navigate"],
            "go to": ["navigate"],
            "open": ["navigate", "get_document"],
            "show me": ["navigate", "list_documents"],
            "how many": ["list_documents"],
            "count": ["list_documents"],
            "list": ["list_documents"],
            "find": ["search_documents", "list_documents"],
            "search": ["search_documents"],
            "create": ["create_document", "get_doctype_info"],
            "add": ["create_document", "get_doctype_info"],
            "new": ["create_document", "get_doctype_info"],
            "update": ["update_document"],
            "change": ["update_document"],
            "edit": ["update_document"],
            "delete": ["delete_document"],
            "remove": ["delete_document"],
            "what is": ["get_document", "get_doctype_info"],
            "get": ["get_document"],
            "schema": ["get_doctype_info"],
            "fields": ["get_doctype_info"],
        }

        scores = {}
        for keyword, tool_names in intent_tools.items():
            if keyword in msg:
                for i, name in enumerate(tool_names):
                    scores[name] = scores.get(name, 0) + (10 - i)

        # Always include navigate and list_documents as fallbacks
        scores.setdefault("navigate", 1)
        scores.setdefault("list_documents", 1)

        # Sort by score, pick top N (minus slots used by dynamic tools)
        static_slots = self.MAX_TOOLS_PER_REQUEST - len(dynamic_schemas)
        ranked = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)
        selected_names = set(ranked[:max(static_slots, 2)])

        selected = [s for s in all_schemas if s["function"]["name"] in selected_names]

        # Combine: dynamic tools first (more specific), then static fallbacks
        combined = dynamic_schemas + selected
        return combined[:self.MAX_TOOLS_PER_REQUEST] or all_schemas[:self.MAX_TOOLS_PER_REQUEST]

    def _get_tool_schemas(self):
        """Convert plugin BaseTool instances to OpenAI function-calling schemas."""
        tools = []

        # Determine which tools this agent has enabled
        enabled_tools = None
        if self._agent_doc and self._agent_doc.tools:
            enabled_tools = [t.tool for t in self._agent_doc.tools if t.enabled]

        all_tools = self.plugin_manager.tools

        for tool_name, tool_instance in all_tools.items():
            if enabled_tools is not None and tool_name not in enabled_tools:
                continue

            # Get JSON Schema for tool parameters
            if hasattr(tool_instance, "args_schema") and tool_instance.args_schema:
                try:
                    schema = tool_instance.args_schema.model_json_schema()
                    schema = self._simplify_tool_schema(schema)
                except Exception:
                    schema = getattr(tool_instance, "inputSchema", {"type": "object", "properties": {}})
            elif hasattr(tool_instance, "inputSchema") and tool_instance.inputSchema:
                schema = tool_instance.inputSchema
            else:
                schema = {"type": "object", "properties": {}}

            # Use compact descriptions for local models
            desc = self._compact_description(tool_instance.name, tool_instance.description)
            tools.append({
                "type": "function",
                "function": {
                    "name": tool_instance.name,
                    "description": desc,
                    "parameters": schema,
                },
            })

        return tools

    @staticmethod
    def _compact_description(name, description):
        """Return a short tool description for local models."""
        compact = {
            "navigate": "Navigate to a page.",
            "list_documents": "List or count documents.",
            "get_document": "Get a document by name.",
            "create_document": "Create a new document.",
            "update_document": "Update a document.",
            "delete_document": "Delete a document.",
            "search_documents": "Search for documents.",
            "get_doctype_info": "Get DocType field schema.",
            "frappe_utils": "Run a utility function.",
        }
        return compact.get(name, (description or "")[:80])

    @staticmethod
    def _simplify_tool_schema(schema):
        """Flatten Pydantic anyOf wrappers so LLMs can parse tool schemas.

        Pydantic wraps Optional[str] as {"anyOf": [{"type": "string"}, {"type": "null"}]}.
        Most LLMs (especially local ones) expect simple {"type": "string"}.
        """
        schema.pop("title", None)
        schema.pop("$defs", None)

        props = schema.get("properties", {})
        for key, prop in props.items():
            prop.pop("title", None)
            prop.pop("default", None)

            # Flatten anyOf: [{type: X}, {type: null}] → {type: X}
            if "anyOf" in prop:
                any_of = prop["anyOf"]
                non_null = [t for t in any_of if t.get("type") != "null"]
                if len(non_null) == 1:
                    # Preserve description before replacing
                    desc = prop.get("description")
                    prop.clear()
                    prop.update(non_null[0])
                    if desc:
                        prop["description"] = desc

        return schema

    def _execute_tool(self, name, arguments):
        """Execute a named tool. Returns (result_json_string, action_dict_or_none).

        Checks static plugin tools first, then falls back to dynamic tools
        generated by the tool factory.
        """
        try:
            # 1. Try static plugin tools first
            tool = self.plugin_manager.get_tool(name)
            if tool:
                result = tool._safe_execute(arguments)
            else:
                # 2. Try dynamic tools from tool factory
                result = self._execute_dynamic_tool(name, arguments)
                if result is None:
                    return json.dumps({"error": f"Tool '{name}' not found"}), None

            # Detect navigation/action in result
            action = None
            if isinstance(result, dict) and result.get("action"):
                action = result
            elif isinstance(result, dict) and isinstance(
                result.get("result"), dict
            ):
                inner = result["result"]
                if inner.get("action"):
                    action = inner

            return json.dumps(result, default=str), action

        except Exception as e:
            frappe.log_error(f"Tool execution error ({name}): {e}")
            return json.dumps({"error": str(e)}), None

    def _execute_dynamic_tool(self, name, arguments):
        """Execute a dynamically generated tool by name. Returns result dict or None."""
        try:
            from tb_owlai_core.intelligence.tool_factory import generate_dynamic_tools, execute_dynamic_tool
            dynamic_tools = generate_dynamic_tools()
            if name in dynamic_tools:
                return execute_dynamic_tool(dynamic_tools[name], arguments)
        except Exception as e:
            logger.error(f"Dynamic tool execution error ({name}): {e}")
        return None

    def _drain_side_channel_actions(self):
        """Collect and clear actions queued by tools via frappe.local.owlai_actions."""
        actions = []
        if hasattr(frappe.local, "owlai_actions") and frappe.local.owlai_actions:
            actions = list(frappe.local.owlai_actions)
            frappe.local.owlai_actions = []
        return actions


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _accumulate_usage(total, new):
    """Sum token usage dicts."""
    if not new:
        return
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        total[key] = total.get(key, 0) + (new.get(key, 0) or 0)


def _format_actions(actions):
    """Convert raw action dicts to frontend-compatible format."""
    formatted = []
    for a in actions:
        formatted.append({
            "name": a.get("action", "navigate"),
            "parameters": a,
        })
    return formatted
