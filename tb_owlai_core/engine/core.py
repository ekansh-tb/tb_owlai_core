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
from tb_owlai_core.utils.plugin_manager import PluginManager, get_plugin_manager

logger = frappe.logger("owlai.engine")


class OwlEngine:
    """Frappe-native AI agent. Sees what the user sees, does what the user can do."""

    def __init__(self, user=None, conversation_id=None, agent_name=None):
        self.user = user or frappe.session.user
        self.conversation = conv_store.load_or_create(conversation_id, self.user)
        self.plugin_manager = get_plugin_manager()
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
        start_time = time.time()

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
        force_text_next = False  # After text interception or error, force text mode
        had_tool_error = False

        for _round in range(self.max_tool_rounds):
            # Send tools only if not forced into text mode
            current_tools = [] if force_text_next else tools

            # If forcing text, inject summarization instruction
            if force_text_next:
                messages.append({
                    "role": "system",
                    "content": "Summarize the tool results for the user in plain language. Do NOT call tools again. If there was an error, explain what went wrong and what information you need from the user."
                })

            response = self.client.chat(messages, tools=current_tools)
            _accumulate_usage(usage_total, response.usage)

            # If we forced text mode, we're done — take the response as-is
            if force_text_next:
                break

            # Intercept: model may output tool calls as text instead of using API
            if not response.has_tool_calls and response.content:
                enabled = set(self._get_enabled_tool_names())
                text_calls = _extract_text_tool_calls(response.content, enabled)
                if text_calls:
                    response.tool_calls = text_calls
                    response.content = ""
                    force_text_next = True  # Next round: no tools, force summary

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

                # Check if tool returned an error — force text summary next round
                try:
                    result_obj = json.loads(result_str)
                    if isinstance(result_obj, dict) and (
                        not result_obj.get("success", True)
                        or result_obj.get("error")
                        or (isinstance(result_obj.get("result"), dict) and result_obj["result"].get("status") == "Incomplete")
                    ):
                        had_tool_error = True
                except (json.JSONDecodeError, TypeError):
                    pass

                # Format result for better LLM comprehension
                formatted_result = _format_tool_result_for_llm(result_str)
                messages.append(
                    self.client.format_tool_result_message(tc["id"], formatted_result)
                )
                # Persist tool result message (original, not formatted)
                conv_store.save_message(
                    self.conversation, "tool", result_str,
                    message_type="tool_result",
                    tool_call_id=tc["id"],
                    tool_name=tc["name"]
                )

            # If any tool had an error, force text mode next round
            if had_tool_error:
                force_text_next = True

        reply = response.content if response else ""

        # Collect side-channel actions (navigate, reload, etc.)
        actions.extend(self._drain_side_channel_actions())

        # Format actions for frontend
        action_data = _format_actions(actions) if actions else None

        # Save assistant response with metrics
        elapsed_ms = int((time.time() - start_time) * 1000)
        model_name = getattr(self.client, 'model', None)
        conv_store.save_message(
            self.conversation,
            "assistant",
            reply,
            message_type="action" if actions else "text",
            action_data={"actions": action_data} if action_data else None,
            model_used=model_name,
            tokens_used=usage_total.get("total_tokens"),
            response_time_ms=elapsed_ms,
        )
        frappe.db.commit()

        return {
            "reply": reply,
            "action_data": action_data,
            "conversation_id": self.conversation.name,
            "usage": usage_total,
        }

    def run_stream(self, message, context=None):
        """Streaming agent execution. Yields SSE-formatted strings."""
        context = context or OwlContext()
        start_time = time.time()

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

        # Disambiguation: run entity resolver and surface matches before LLM
        disambig_payload = _build_disambiguation_payload(message)
        if disambig_payload:
            yield f"data: {json.dumps({'disambiguation': disambig_payload})}\n\n"

        force_text_next = False  # After text interception or error, force text mode
        shown_working = False    # Only show "Working on it..." once

        try:
            for _round in range(self.max_tool_rounds):
                content_buffer = ""
                pending_tokens = []
                tool_calls = []
                had_tool_error = False

                # Send tools only if not forced into text mode
                current_tools = [] if force_text_next else tools

                # If forcing text, inject summarization instruction
                if force_text_next:
                    messages.append({
                        "role": "system",
                        "content": "Summarize the tool results for the user in plain language. Do NOT call tools again. If there was an error, explain what went wrong and what information you need from the user."
                    })

                try:
                    stream_iter = self.client.chat_stream(messages, tools=current_tools)
                except Exception as init_err:
                    yield f"data: {json.dumps({'token': f'[Stream init error: {init_err}]'})}\n\n"
                    break

                # When no tools possible, stream immediately (no buffering needed)
                buffer_mode = bool(current_tools)

                for chunk in stream_iter:
                    if chunk.get("content"):
                        content_buffer += chunk["content"]
                        if buffer_mode:
                            pending_tokens.append(chunk["content"])
                        else:
                            # Stream immediately — no tool interception needed
                            yield f"data: {json.dumps({'token': chunk['content']})}\n\n"

                    if chunk.get("done"):
                        tool_calls = chunk.get("tool_calls", [])
                        _accumulate_usage(usage_total, chunk.get("usage", {}))

                # Intercept: model may output tool calls as text
                if not tool_calls and content_buffer and buffer_mode:
                    enabled = set(self._get_enabled_tool_names())
                    text_calls = _extract_text_tool_calls(content_buffer, enabled)
                    if text_calls:
                        tool_calls = text_calls
                        content_buffer = ""
                        pending_tokens = []
                        force_text_next = True  # Next round: force text summary
                        if not shown_working:
                            yield f"data: {json.dumps({'token': 'Working on it...'})}\n\n"
                            shown_working = True

                # Flush buffered tokens if no tool calls were detected
                if not tool_calls and pending_tokens:
                    for token in pending_tokens:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                pending_tokens = []

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

                        # Check if tool returned an error
                        try:
                            result_obj = json.loads(result_str)
                            if isinstance(result_obj, dict) and (
                                not result_obj.get("success", True)
                                or result_obj.get("error")
                                or (isinstance(result_obj.get("result"), dict) and result_obj["result"].get("status") == "Incomplete")
                            ):
                                had_tool_error = True
                        except (json.JSONDecodeError, TypeError):
                            pass

                        # Format result for better LLM comprehension
                        formatted_result = _format_tool_result_for_llm(result_str)
                        messages.append(
                            self.client.format_tool_result_message(
                                tc["id"], formatted_result
                            )
                        )
                        # Persist tool result message (original)
                        conv_store.save_message(
                            self.conversation, "tool", result_str,
                            message_type="tool_result",
                            tool_call_id=tc["id"],
                            tool_name=tc["name"]
                        )

                    # If any tool errored, force text summary next round
                    if had_tool_error:
                        force_text_next = True
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
            # Persist assistant response with metrics
            try:
                elapsed_ms = int((time.time() - start_time) * 1000)
                model_name = getattr(self.client, 'model', None)
                action_data = _format_actions(actions) if actions else None
                conv_store.save_message(
                    self.conversation,
                    "assistant",
                    full_response,
                    message_type="action" if actions else "text",
                    action_data={"actions": action_data} if action_data else None,
                    model_used=model_name,
                    tokens_used=usage_total.get("total_tokens"),
                    response_time_ms=elapsed_ms,
                )
                frappe.db.commit()
            except Exception as e:
                frappe.log_error(f"Failed to save assistant response: {e}")

            yield "event: end\ndata: [DONE]\n\n"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    # Token budget: max total chars across all messages before trimming older ones
    MAX_CONTEXT_CHARS = 24000  # ~6000 tokens for 7B models with 8K context
    TOOL_EXECUTION_TIMEOUT = 30  # seconds

    def _build_messages(self, user_message, context):
        """Assemble the full message list for the LLM.

        Note: The current user message is already saved to the conversation
        before this method is called, so get_history() already includes it.
        We do NOT append it again to avoid duplication.

        Applies token budget guard: trims older messages if total exceeds threshold.
        """
        messages = [{"role": "system", "content": self._build_system_prompt(context, user_message)}]
        history = conv_store.get_history(self.conversation)

        # Token budget guard: trim older messages if exceeding context window
        total_chars = sum(len(m.get("content", "")) for m in messages)
        trimmed_history = []
        for msg in reversed(history):
            msg_chars = len(msg.get("content", ""))
            if total_chars + msg_chars > self.MAX_CONTEXT_CHARS and trimmed_history:
                break
            trimmed_history.append(msg)
            total_chars += msg_chars

        trimmed_history.reverse()
        messages.extend(trimmed_history)
        return messages

    def _build_system_prompt(self, context, user_message=None):
        """Dynamic system prompt that adapts to ANY Frappe site. Zero hardcoded DocTypes.

        Uses multi-layer context from bench introspection:
        1. Business domain context (from Redis cache)
        2. User context (roles, company, defaults)
        3. Viewport context (current route, schema, form data)
        4. Knowledge context (RAG results for the query)
        5. Tool guidance with dynamic examples
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

        # Layer 5: Tool usage guidance with dynamic examples
        tool_guidance = self._build_tool_guidance()

        # Layer 6: Dynamic few-shot examples from detected DocTypes
        examples = self._build_dynamic_examples(user_message, context)

        # Layer 7: Entity context (resolved names from user message)
        entity_ctx = ""
        if user_message and context:
            entity_ctx = context.get_entity_context(user_message)

        # Layer 8: Enhanced prompt templates (multi-step, language, financial)
        enhanced_prompt = ""
        try:
            from tb_owlai_core.intelligence.prompt_templates import get_full_enhanced_prompt
            enhanced_prompt = get_full_enhanced_prompt()
        except Exception:
            pass

        # Layer 9: User defaults context
        defaults_ctx = context.get_user_defaults_context() if context else ""

        # Token budget: keep total under ~2000 tokens
        if len(domain_ctx) > 800:
            domain_ctx = domain_ctx[:800]
        if len(viewport) > 2000:
            viewport = viewport[:2000]
        if len(knowledge_ctx) > 1200:
            knowledge_ctx = knowledge_ctx[:1200]
        if len(enhanced_prompt) > 1500:
            enhanced_prompt = enhanced_prompt[:1500]

        return f"""You are OwlAI, an intelligent assistant for Frappe site: {site}.

RULES:
1. ALWAYS use tool calls to answer questions — never describe what you would do, just do it.
2. If a tool returns an error, STOP calling tools. Explain the error to the user and ask for missing info.
3. After getting tool results, respond with a natural language summary.
4. Never retry a failed tool call with the same arguments.
5. Respond in the same language the user writes in (Hindi, Hinglish, English, etc.).{custom_prompt}{domain_ctx}{user_ctx}{defaults_ctx}{tool_guidance}{examples}{entity_ctx}{enhanced_prompt}
{viewport}{knowledge_ctx}"""

    def _build_dynamic_examples(self, user_message=None, context=None):
        """Generate contextual few-shot examples from detected DocTypes — zero hardcoding."""
        examples = []

        # Get a sample DocType from the current context or message
        sample_dt = None
        if context and context.doctype:
            sample_dt = context.doctype
        elif user_message:
            try:
                from tb_owlai_core.intelligence.bench_introspector import detect_doctypes_in_text
                detected = detect_doctypes_in_text(user_message)
                if detected:
                    sample_dt = detected[0]
            except Exception:
                pass

        if not sample_dt:
            # Pick from bench categories dynamically
            try:
                from tb_owlai_core.intelligence.bench_introspector import get_bench_map
                bench_map = get_bench_map()
                if bench_map:
                    cats = bench_map.get("domain_categories", {})
                    # Pick first available from people > transactions > masters
                    for cat in ("people", "transactions", "masters"):
                        items = cats.get(cat, [])
                        if items:
                            sample_dt = items[0]
                            break
            except Exception:
                pass

        if not sample_dt:
            return ""

        # Build examples dynamically from the discovered DocType
        enabled = self._get_enabled_tool_names()
        lines = ["\nEXAMPLES:"]

        if "list_documents" in enabled:
            lines.append(f'- To count {sample_dt} records → call list_documents(doctype="{sample_dt}", limit_page_length=0)')
        if "navigate" in enabled:
            lines.append(f'- To open {sample_dt} list → call navigate(doctype="{sample_dt}", view="list")')
        if "create_document" in enabled:
            lines.append(f'- To create a {sample_dt} → call create_document(doctype="{sample_dt}", data={{...}})')

        lines.append("- If a tool returns missing fields, tell the user which fields are needed — do NOT retry.")

        return "\n".join(lines)

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
            "get_account_balance": "Get account/cash/bank balance. Use for balance sheet queries.",
            "get_party_outstanding": "Get outstanding receivables/payables for a customer or supplier.",
            "get_general_ledger": "Get GL entries / ledger for an account or party.",
            "get_sales_summary": "Get sales revenue summary by period, customer, or item.",
            "get_stock_balance": "Get current stock/inventory levels for an item or warehouse.",
            "ensure_exists": "Find a record or create it if missing (get-or-create).",
            "ui_actuator": "Execute a sequence of visible UI actions: navigate, fill fields, save. Use for visual automation.",
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
            # Financial intelligence
            "balance": ["get_account_balance"],
            "cash": ["get_account_balance"],
            "bank": ["get_account_balance"],
            "outstanding": ["get_party_outstanding"],
            "receivable": ["get_party_outstanding"],
            "payable": ["get_party_outstanding"],
            "ledger": ["get_general_ledger"],
            "gl": ["get_general_ledger"],
            "sales": ["get_sales_summary"],
            "revenue": ["get_sales_summary"],
            "stock": ["get_stock_balance"],
            "inventory": ["get_stock_balance"],
            "payment": ["get_party_outstanding"],
            # UI Automation
            "fill": ["ui_actuator"],
            "automate": ["ui_actuator"],
            "open and fill": ["ui_actuator"],
            "set value": ["ui_actuator"],
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
            "get_account_balance": "Get account/bank/cash balance.",
            "get_party_outstanding": "Get outstanding receivables/payables.",
            "get_general_ledger": "Get GL entries for an account.",
            "get_sales_summary": "Get sales revenue summary.",
            "get_stock_balance": "Get stock/inventory levels.",
            "ensure_exists": "Find or create a record.",
            "ui_actuator": "UI automation sequence.",
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
        generated by the tool factory. Enforces execution timeout.
        """
        import signal

        def _timeout_handler(signum, frame):
            raise TimeoutError(f"Tool '{name}' timed out after {self.TOOL_EXECUTION_TIMEOUT}s")

        try:
            # Set execution timeout (Unix only, graceful fallback on other OS)
            old_handler = None
            try:
                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(self.TOOL_EXECUTION_TIMEOUT)
            except (AttributeError, ValueError):
                pass  # signal.SIGALRM not available (Windows) or not main thread

            # 1. Try static plugin tools first
            tool = self.plugin_manager.get_tool(name)
            if tool:
                result = tool._safe_execute(arguments)
            else:
                # 2. Try dynamic tools from tool factory
                result = self._execute_dynamic_tool(name, arguments)
                if result is None:
                    return json.dumps({"error": f"Tool '{name}' not found"}), None

            # Cancel timeout
            try:
                signal.alarm(0)
                if old_handler is not None:
                    signal.signal(signal.SIGALRM, old_handler)
            except (AttributeError, ValueError):
                pass

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


def _build_disambiguation_payload(message):
    """Run entity resolver on the message and build a disambiguation payload.

    Returns a dict with 'entities', 'suggested_actions', and 'message' keys
    when multiple entities are found, or None if no disambiguation is needed.
    """
    try:
        from tb_owlai_core.intelligence.entity_resolver import resolve_entities
    except ImportError:
        return None

    try:
        matches = resolve_entities(message)
    except Exception:
        return None

    if not matches:
        return None

    # Only surface disambiguation when there are 2+ distinct entities or
    # the top match is ambiguous (confidence < 1.0 and multiple results).
    top_confidence = matches[0]["confidence"] if matches else 0
    if len(matches) == 1 and top_confidence >= 1.0:
        return None  # Exact single match — no disambiguation needed

    # Cap at 5 entities to keep the UI clean
    entities = []
    for m in matches[:5]:
        entities.append({
            "doctype": m["doctype"],
            "name": m["name"],
            "display_name": m.get("display") or m["name"],
            "confidence": round(m["confidence"], 2),
        })

    # Build intent-level suggested actions for vague queries (no strong match)
    suggested_actions = []
    if top_confidence < 0.7 and entities:
        doctype = entities[0]["doctype"]
        suggested_actions = [
            {"label": f"View {doctype} List", "action": "navigate_list", "doctype": doctype},
            {"label": f"Create New {doctype}", "action": "navigate_new", "doctype": doctype},
            {"label": f"Search {doctype}s", "action": "search", "query": f"search {doctype.lower()} "},
        ]

    return {
        "message": "Multiple matches found — which did you mean?",
        "entities": entities,
        "suggested_actions": suggested_actions,
    }


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


def _extract_text_tool_calls(text, enabled_tools=None):
    """Extract tool calls that the model wrote as text instead of using the API.

    Local 7B models sometimes output tool calls as text like:
    - [{"name":"list_documents","arguments":{"doctype":"Employee"}}]
    - list_documents(doctype="Employee", limit_page_length=0)
    - [TOOL_CALLS] [{"name":"list_documents",...}]

    Args:
        text: The model's text output to scan.
        enabled_tools: Set of tool names this agent is allowed to use.
            Only tools in this set will be extracted. Security: prevents
            text-format tool calls from bypassing the agent's tool allowlist.

    Returns list of {"id": str, "name": str, "arguments": dict} or empty list.
    """
    import re

    if not text:
        return []

    known_tools = {"list_documents", "get_document", "create_document",
                  "update_document", "delete_document", "search_documents",
                  "navigate", "get_doctype_info", "frappe_utils",
                  "get_account_balance", "get_party_outstanding", "get_general_ledger",
                  "get_sales_summary", "get_stock_balance", "ensure_exists",
                  "ui_actuator"}

    # Intersect with enabled tools if provided — security gate
    allowed = known_tools & enabled_tools if enabled_tools else known_tools

    # Pattern 1: JSON array of tool calls
    # Matches: [{"name":"tool_name","arguments":{...}}]
    json_pattern = r'\[?\s*\{["\']name["\']\s*:\s*["\'](\w+)["\'].*?["\']arguments["\']\s*:\s*(\{[^}]*\})'
    matches = re.findall(json_pattern, text, re.DOTALL)
    if matches:
        calls = []
        for name, args_str in matches:
            if name not in allowed:
                continue
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}
            calls.append({
                "id": f"text_call_{len(calls)}",
                "name": name,
                "arguments": args,
            })
        return calls

    # Pattern 2: Function-call syntax
    # Matches: tool_name(arg1="val1", arg2=val2)
    EXPLANATORY_PHRASES = [
        "you can use", "try calling", "for example", "e.g.", "such as",
        "like ", "by using", "by calling",
    ]
    func_pattern = r'(\w+)\(([^)]+)\)'
    for match in re.finditer(func_pattern, text):
        func_name = match.group(1)
        args_str = match.group(2)

        if func_name not in allowed:
            continue

        # Skip false positives: explanatory context before the match
        start = match.start()
        context_before = text[max(0, start - 50):start].lower()
        if any(phrase in context_before for phrase in EXPLANATORY_PHRASES):
            continue

        # Skip if match is inside inline backticks (e.g. `navigate(...)`)
        # but NOT code fence blocks (```...```) — LLMs often put tool calls in code blocks
        prefix = text[:start]
        if start > 0 and prefix.rstrip().endswith('`'):
            # Check: is this a single inline backtick or a code fence?
            stripped = prefix.rstrip()
            if not stripped.endswith('```'):
                # Single inline backtick — likely explanatory, skip
                continue

        # Parse keyword arguments
        args = {}
        for kv in re.finditer(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\d+)|(\w+))', args_str):
            key = kv.group(1)
            val = kv.group(2) or kv.group(3) or kv.group(4) or kv.group(5)
            if val and val.isdigit():
                val = int(val)
            args[key] = val

        if args:
            return [{
                "id": f"text_call_0",
                "name": func_name,
                "arguments": args,
            }]

    return []


def _format_tool_result_for_llm(result_str):
    """Format tool results for better LLM comprehension.

    Converts verbose JSON into concise summaries that help the model
    generate better natural-language responses.
    """
    try:
        result = json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return result_str

    if not isinstance(result, dict):
        return result_str

    # Error results — make the error message prominent
    if not result.get("success", True) or result.get("error"):
        error = result.get("error", "Unknown error")
        return f"ERROR: {error}. Tell the user about this error and ask for the missing information."

    inner = result.get("result", result)

    # Incomplete results (missing mandatory fields)
    if isinstance(inner, dict) and inner.get("status") == "Incomplete":
        missing = inner.get("missing_fields", [])
        field_names = [f.get("label", f.get("fieldname", "?")) for f in missing] if isinstance(missing, list) else []
        msg = inner.get("message", "Missing required fields")
        return f"INCOMPLETE: {msg}. Missing fields: {', '.join(field_names)}. Ask the user to provide these values."

    # List results — summarize count and preview
    if isinstance(inner, dict) and "data" in inner:
        data = inner["data"]
        count = inner.get("count", len(data) if isinstance(data, list) else 0)
        doctype = inner.get("doctype", "records")
        if count == 0:
            return f"No {doctype} records found."
        preview = json.dumps(data[:5], default=str) if isinstance(data, list) else str(data)
        if len(preview) > 1500:
            preview = preview[:1500] + "..."
        return f"Found {count} {doctype} record(s). Data: {preview}"

    # Navigation/action results
    if isinstance(inner, dict) and inner.get("action"):
        action = inner.get("action")
        msg = inner.get("message", "")
        return f"Action: {action}. {msg}"

    # Default: truncate if too long
    text = json.dumps(result, default=str)
    if len(text) > 2000:
        return text[:2000] + "..."
    return text
