# OwlAI Core — Enterprise Refactor Plan v2

## Vision

**OwlAI = The user's intelligent proxy inside Frappe/ERPNext.**

OwlAI can see what the session user sees, can do what the session user can do — and nothing more. It operates entirely within Frappe's RBAC. It works out of the box on any Frappe/ERPNext site with zero configuration. Local LLM (Ollama) is the primary engine. Cloud providers are fallback only.

### Core Principles

1. **Frappe-Native** — No mandatory third-party AI frameworks. No agno, no crewai, no litellm, no langchain as hard dependencies. Direct HTTP calls to Ollama/OpenAI-compatible APIs using `requests`.
2. **Local-First** — Ollama is the default. Cloud LLM providers (OpenAI, Anthropic, Groq, OpenRouter) are optional fallbacks configured via OwlAI Provider DocType.
3. **RBAC-Enforced** — Every tool call goes through `frappe.has_permission()`. `ignore_permissions=True` is NEVER used for user-facing operations. The AI cannot escalate privileges.
4. **Zero-Config** — Install the app, run `bench migrate`, if Ollama is running with any model, OwlAI works. No API keys, no setup wizard, no manual agent configuration needed.
5. **Generic** — No hardcoded DocType names, no ERPNext-specific assumptions, no company-specific branding. Works on a bare Frappe site with zero modules installed.
6. **Action-Oriented** — OwlAI doesn't just chat. It navigates the user's browser (via Frappe JS API), creates/reads/updates/deletes documents, runs workflows, submits forms — all within the user's permission scope.

---

## Current State Analysis

### What's Good (Keep)
- **Plugin-based tool system** (`plugins/base.py`, `plugins/core/tools/*`) — Well-structured, Pydantic-validated, permission-checked. This is the backbone.
- **OwlContext** (`utils/context.py`) — Route parsing, schema extraction, form data awareness. Needs cleanup but solid concept.
- **Context builder** (`agno_integrations/context_builder.py`) — Company/user/system context injection. Good idea, needs decouple from agno.
- **OwlAI DocTypes** — Provider, Model, Agent, Tool, Conversation, Settings, Analytics. Good data model.
- **Navigate tool + frontend action dispatch** — `frappe.local.owlai_actions` pattern for sending navigation commands to the browser.
- **Tool permission checking** — `BaseTool.check_permission()` + individual tools checking `frappe.has_permission()`.
- **Cache utility** (`utils/cache.py`) — Simple Redis-backed cache via Frappe. Works.
- **Auto-discovery** (`config/auto_discovery.py`) — Scans env vars for API keys, registers providers. Good for zero-config.

### What's Wrong (Fix/Remove)

#### Hard Dependencies on Third-Party AI Frameworks
| Framework | Files | Usage | Verdict |
|-----------|-------|-------|---------|
| **agno** | 15 files, ~40 imports | Agent loop, storage adapter, model factory, toolkit wrapper, compression, knowledge chunking, embeddings | **REMOVE as hard dep.** Replace with native LLM client (~200 lines). |
| **crewai** | 4 files | Multi-agent crews | **REMOVE entirely.** Dead feature — crew DocType exists but not used in production flow. |
| **litellm** | 2 files | `router.py` import (unused), `transcriber.py` (cloud whisper fallback) | **REMOVE.** Router import is dead code. Transcription can use direct OpenAI API. |
| **lancedb** | 1 file | Vector DB for RAG knowledge index | **MAKE OPTIONAL.** RAG is nice-to-have, not core. Guard with try/except. |
| **chromadb** | 0 files | In requirements.txt but never imported | **REMOVE from requirements.** |
| **tantivy** | 0 files | In requirements.txt but never imported | **REMOVE from requirements.** |

#### Security Holes
| Issue | Location | Severity |
|-------|----------|----------|
| `ignore_permissions=True` after permission check | `create_document.py:139`, `update_document.py:42` | **CRITICAL** — Permission check is a no-op |
| No ownership check on conversation delete | `router.py:641` | **HIGH** — Any user can delete any conversation |
| No role check on settings update | `router.py:583` | **HIGH** — Any user can change global AI config |
| Arbitrary code execution via DB method path | `tool_registry.py:122` | **HIGH** — Compromised Tool record = RCE |
| SQL injection in vector DB delete | `knowledge_index.py:175` | **MEDIUM** — String-interpolated filter |
| 25+ bare `except:` clauses | 15 files | **MEDIUM** — Silent failures, invisible bugs |
| Arbitrary method call on documents | `run_doc_method.py:49-57` | **MEDIUM** — Calls any method on a doc with write perm |
| `sandbox.py` exposes `safe_exec` to AI | `sandbox.py:26` | **MEDIUM** — AI can execute arbitrary Python |

#### Architectural Duplication
| Duplicate | Files | Verdict |
|-----------|-------|---------|
| Two agent systems | `owlai_core/agent.py` (dead) vs `agno_integrations/main.py` (active) | Delete dead one, replace active one with native client |
| Two LLM factories | `utils/llm_factory.py` (dead) vs `agno_integrations/model_factory.py` (active) | Delete both, replace with native HTTP client |
| Two toolkit adapters | `owlai_core/agno_adapter.py` vs `agno_integrations/tools.py` | Delete both, tools called directly via ToolRegistry |
| ~22 dead debug/migration scripts | `agno_check.py`, `check_*.py`, `debug_*.py`, `fix_*.py`, `verify_*.py`, etc. | Delete all |

#### Hardcoded Values (Not Generic)
| Hardcode | Location | Fix |
|----------|----------|-----|
| `"llama3-70b-8192"`, `"gpt-4o"`, `"claude-3-5-sonnet-..."`, `"llama3.2:3b"` | `auto_discovery.py`, `model_factory.py`, `setup_defaults.py` | Discover from Ollama API or Provider DocType |
| `"http://localhost:11434"` | 5+ files | `OwlAI Provider.api_base` or `OLLAMA_HOST` env |
| `"Sales Order"`, `"Task"`, `"ToDo"` field lists | `tools.py:150`, `router.py:407`, `context_builder.py:135` | Use `frappe.get_meta()` dynamically |
| Legacy Settings fields | `gemini_api_key`, `gemini_model`, `ollama_url`, `provider` (string) | Remove, use Provider/Model DocType system |

---

## Target Architecture

```
+----------------------------------------------------------+
|                    FRAPPE DESK (Browser)                  |
|  OwlNest UI --> frappe.call() --> SSE Stream              |
|  <-- frappe.set_route() / cur_frm.reload_doc()           |
+------------------------+---------------------------------+
                         | @frappe.whitelist()
+------------------------v---------------------------------+
|                    API LAYER (router.py)                  |
|  handle_chat() --> OwlEngine.run()                       |
|  Auth: frappe.session.user, rate limiting                 |
+------------------------+---------------------------------+
                         |
+------------------------v---------------------------------+
|                    OWL ENGINE (NEW: engine.py)            |
|  1. Build context (user, route, schema, form data)       |
|  2. Build messages (system prompt + history + user msg)   |
|  3. Call LLM (Ollama HTTP API / OpenAI-compatible)       |
|  4. If tool_call -> execute tool -> feed result -> loop   |
|  5. Stream tokens back via SSE                           |
|  Native Python. No frameworks. ~300 lines.               |
+------+---------------------------+-----------------------+
       |                           |
+------v----------+    +-----------v-----------------------+
|   LLM CLIENT    |    |         TOOL REGISTRY             |
|  (NEW: llm.py)  |    |   (existing: tool_registry.py)    |
|                 |    |                                    |
| - Ollama API    |    |  PluginManager -> BaseTool.execute |
| - OpenAI API    |    |  Permission check per tool         |
| - Streaming     |    |  Pydantic validation               |
| - Tool-use      |    |                                    |
|   protocol      |    |  Tools:                            |
| - Retry logic   |    |  - get_doctype_info                |
|                 |    |  - list_documents                  |
| ~150 lines.     |    |  - get_document                    |
| Zero deps       |    |  - create_document                 |
| beyond requests |    |  - update_document                 |
+-----------------+    |  - delete_document                 |
                       |  - search_documents                |
                       |  - navigate (-> JS route change)   |
                       |  - run_doc_method (submit/cancel)  |
                       |  - run_workflow                    |
                       |  - frappe_utils                    |
                       +-----------------------------------+
```

### Key Design Decisions

**1. Native LLM Client (replaces agno Agent, litellm, model_factory)**

Instead of `agno.Agent` which adds ~50 transitive dependencies, we write a thin HTTP client that:
- Calls Ollama's `/api/chat` endpoint (supports tool calling natively)
- Falls back to OpenAI-compatible `/v1/chat/completions` for cloud providers
- Handles streaming (SSE), tool-call loop, retry logic
- ~150 lines of Python using only `requests` (already in Frappe)

**2. Tool Execution via Existing Plugin System (replaces FrappeToolkit, OwlAIToolkit)**

The tools already exist as proper `BaseTool` subclasses with Pydantic schemas and permission checks. Instead of wrapping them in agno's `Toolkit`, we:
- Convert each tool's Pydantic schema to OpenAI function-calling format (trivial)
- When LLM returns a `tool_call`, look up the tool in `ToolRegistry`, call `_safe_execute()`
- Feed result back to LLM as a tool response message
- No framework needed for this loop

**3. Conversation History via Frappe DocType (replaces agno Storage)**

`OwlAI Conversation` + `OwlAI Message` child table already stores messages. Instead of the 316-line `FrappeStorage` adapter that translates between agno's session model and Frappe, we:
- Load last N messages directly from the child table
- Save new messages directly to the child table
- ~30 lines of code

**4. Context is King — OwlAI Sees What You See**

The AI's power comes from knowing what the user is looking at:
- **Route context**: parsed from `frappe.get_route()` -> knows the DocType, document name, view type
- **Schema context**: `frappe.get_meta(doctype)` -> knows fields, types, mandatory, options
- **Form data**: sent from frontend -> knows current form values
- **User context**: `frappe.session.user`, roles, default company
- **Permission context**: what the user can read/write/create/delete

All of this is already partially implemented. We clean it up and make it the foundation.

**5. Frontend Actions via Frappe JS API**

When the AI decides to navigate the user somewhere or reload a form:
- Tool returns an action dict: `{"action": "navigate", "doctype": "Sales Order", "docname": "SO-001"}`
- Router streams it as a special SSE event
- Frontend JS calls `frappe.set_route("Form", "Sales Order", "SO-001")`
- Also supports: `cur_frm.reload_doc()`, `frappe.new_doc()`, `frappe.show_alert()`

This pattern already works. We keep it, clean it up.

---

## Implementation Phases

### Phase 1: New Core Engine (Replace Framework Dependencies)

**Create `tb_owlai_core/engine/llm.py` — Native LLM Client**

```python
class OllamaClient:
    """Direct HTTP client for Ollama /api/chat endpoint."""
    def __init__(self, host, model):
        ...
    def chat(self, messages, tools=None, stream=False):
        """Returns dict with content + tool_calls, or yields stream chunks."""
        ...
    def chat_stream(self, messages, tools=None):
        """Generator that yields tokens and tool calls."""
        ...

class OpenAIClient:
    """For cloud providers. Uses /v1/chat/completions."""
    def __init__(self, api_base, api_key, model):
        ...
    def chat(self, messages, tools=None, stream=False):
        ...

def get_client(model_doc=None, provider_doc=None):
    """Factory. Auto-detects best available LLM.
    No args = try Ollama first, then check env vars for cloud keys.
    With model_doc = use the linked provider."""
    ...
```

**Create `tb_owlai_core/engine/core.py` — The Owl Engine**

```python
class OwlEngine:
    """The agent loop. Zero framework dependencies."""

    def __init__(self, user, conversation_id=None):
        self.user = user
        self.client = self._resolve_client()
        self.registry = ToolRegistry()
        self.conversation = self._load_conversation(conversation_id)
        self.max_tool_rounds = 5

    def run(self, message, context: OwlContext, stream=False):
        """
        1. Build system prompt from user's actual environment
        2. Load conversation history (last N messages)
        3. Append user message
        4. Call LLM with tool schemas
        5. If tool_call -> execute tool -> append result -> call LLM again
        6. Loop max N times
        7. Return/stream final response
        8. Save all messages to conversation
        """

    def run_stream(self, message, context: OwlContext):
        """SSE streaming version of run(). Yields tokens + actions."""

    def _build_system_prompt(self, context: OwlContext):
        """Dynamic prompt from user environment. No hardcoded DocTypes."""

    def _get_tool_schemas(self):
        """Convert BaseTool Pydantic schemas to OpenAI function-call format."""

    def _execute_tool(self, name, arguments):
        """ToolRegistry.execute() with RBAC. Returns result string."""
```

**Create `tb_owlai_core/engine/conversation.py` — Simple Storage**

```python
def load_or_create_conversation(conversation_id, user):
    """Get existing (with ownership check) or create new."""

def get_history_messages(conversation, limit=20):
    """Load last N messages as list of dicts."""

def save_message(conversation, role, content, tool_calls=None):
    """Append to child table and save."""
```

### Phase 2: Security Hardening

**S1. Fix `ignore_permissions=True` in user-facing tools**
- `create_document.py:139` -> `doc.insert()` (remove ignore_permissions)
- `update_document.py:42` -> `doc.save()` (remove ignore_permissions)
- Keep `ignore_permissions=True` ONLY for internal engine operations (conversation management, tool sync, auto-discovery)

**S2. Add ownership checks to all `@frappe.whitelist()` endpoints**
```python
@frappe.whitelist()
def delete_conversation(conversation_id):
    conv = frappe.get_doc("OwlAI Conversation", conversation_id)
    if conv.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw("Not your conversation", frappe.PermissionError)
    frappe.delete_doc(...)
```

**S3. Restrict settings endpoints to System Manager**
```python
@frappe.whitelist()
def update_owlai_settings(...):
    frappe.only_for("System Manager")
    ...
```

**S4. Fix `run_doc_method.py` — Whitelist allowed methods**
```python
ALLOWED_DOC_METHODS = {"submit", "cancel", "amend_doc"}
if method not in ALLOWED_DOC_METHODS:
    if not is_whitelisted_method(doc, method):
        return {"error": f"Method '{method}' is not allowed"}
```

**S5. Remove `sandbox.py`** — AI executing arbitrary Python is too dangerous for production.

**S6. Fix all bare `except:` -> `except Exception as e:` with logging (25+ instances)**

**S7. Fix SQL injection in `knowledge_index.py:175`** — Use parameterized query.

**S8. Add method path whitelist in `tool_registry.py:122`** — Only allow paths under `tb_owlai_core.plugins.*`

### Phase 3: Remove Dead Code & Framework Dependencies

**Delete entirely:**
- `agno_integrations/main.py` (replaced by `engine/core.py`)
- `agno_integrations/model_factory.py` (replaced by `engine/llm.py`)
- `agno_integrations/storage.py` (replaced by `engine/conversation.py`)
- `agno_integrations/tools.py` (tools called directly via ToolRegistry)
- `owlai_core/agent.py` (dead code)
- `owlai_core/agno_adapter.py` (dead code)
- `owlai_core/transcriber.py` (litellm dependency)
- `utils/llm_factory.py` (dead code)
- `crewai_integrations/*` (entire directory)
- `api/crew_api.py` (dead code)

**Delete dead scripts (~22 files):**
- `agno_check.py`, `check_agents.py`, `check_rag.py`, `check_rag_deep.py`
- `debug_config.py`, `debug_discovery.py`, `debug_owlai.py`
- `dump_agent_config.py`, `fix_config.py`, `force_register_tools.py`
- `import_opening_balances.py`, `investigate_entities.py`
- `register_crud.py`, `register_run_crew.py`, `reindex_failed.py`
- `setup_partners_assets.py`, `sync_tools.py`, `test_agent.py`
- `update_agent_tools.py`, `verify_agents.py`, `verify_agno_install.py`, `verify_crud.py`

**Make optional with guarded imports:**
- `agno_integrations/knowledge_index.py` -> move to `knowledge/index.py`, guard LanceDB/agno imports
- `agno_integrations/enrich_knowledge.py` -> move to `knowledge/`, guard imports
- `agno_integrations/auto_seed.py` -> move to `knowledge/`, guard imports

**Update `requirements.txt`:**
```
# Core (zero third-party AI deps)
pydantic
beautifulsoup4

# Optional - uncomment for RAG features
# lancedb
# pypdf
```

Note: `requests` is already available via Frappe. `pydantic` is used for tool schema validation.

### Phase 4: Make It Generic (Any Frappe Site)

**G1. Dynamic field discovery (replace all hardcoded DocType field lists)**
```python
def get_smart_fields(doctype):
    """Auto-detect useful fields for any DocType. Zero hardcoding."""
    meta = frappe.get_meta(doctype)
    fields = ["name"]
    if meta.title_field and meta.title_field != "name":
        fields.append(meta.title_field)
    for f in meta.fields:
        if f.fieldname in ("status", "workflow_state") and not f.hidden:
            fields.append(f.fieldname)
        if f.fieldtype == "Currency" and len(fields) < 6:
            fields.append(f.fieldname)
        if f.fieldtype == "Link" and f.reqd and len(fields) < 6:
            fields.append(f.fieldname)
    return fields[:8]
```

**G2. Dynamic system prompt (adapts to ANY Frappe site)**
```python
def build_system_prompt(user, context: OwlContext):
    site = frappe.local.site
    apps = frappe.get_installed_apps()
    user_doc = frappe.get_doc("User", user)
    roles = [r.role for r in user_doc.roles]
    company = frappe.defaults.get_user_default("Company") or "Not Set"

    prompt = f"""You are OwlAI, the intelligent assistant for this Frappe system.

Site: {site}
Installed Apps: {', '.join(apps)}
User: {user_doc.full_name} ({user})
Roles: {', '.join(roles[:10])}
Default Company: {company}

RULES:
- You can see and do what this user can do. Use tools to take action.
- When you create/find records, provide links: [View {{name}}](/app/{{slug}}/{{name}})
- Slug format: 'Sales Order' -> 'sales-order' (lowercase, hyphens)
- Respect permissions. If tool returns permission error, explain to user.
- Use get_doctype_info BEFORE creating documents to check mandatory fields.
- If user says 'this document' or 'submit it', use the viewport context below.

{context.get_full_context_string()}"""
    return prompt
```

**G3. Clean `OwlAI Settings` DocType**
Remove legacy fields: `gemini_section`, `gemini_api_key`, `gemini_model`, `local_llm_section`, `enable_local_llm`, `ollama_url`, `ollama_model`, `provider` (string select).

Keep/add: `enabled`, `default_agent` (Link), `default_model` (Link), `embedding_model`, `enable_analytics`, `enable_caching`, `cache_ttl`, `max_agent_loops`, `context_message_limit`, `rate_limit_per_minute`, `default_temperature`.

**G4. Lightweight `after_migrate` hook**
```python
def after_migrate():
    """Runs on every bench migrate. Must be fast (<2s)."""
    # Only sync tools - no provider/model/agent/KB setup
    try:
        ToolRegistry()._sync_tools()
    except Exception as e:
        frappe.log_error(f"OwlAI tool sync: {e}")
```

Move heavy setup (provider discovery, agent creation, KB seeding) to `after_install` only.

**G5. Auto-discovery that works anywhere**
```python
def discover_and_register_providers():
    """Runs on after_install. Scans environment."""
    # 1. Check Ollama (zero-config local)
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        resp = requests.get(f"{ollama_host}/api/tags", timeout=2)
        if resp.ok:
            _ensure_provider("Ollama", api_base=ollama_host)
            for m in resp.json().get("models", []):
                _ensure_model(m["name"], "Ollama")
    except Exception:
        pass

    # 2. Check env vars for cloud providers (optional fallback)
    env_providers = {
        "GROQ_API_KEY": "Groq",
        "OPENAI_API_KEY": "OpenAI",
        "ANTHROPIC_API_KEY": "Anthropic",
        "OPEN_ROUTER_API_KEY": "OpenRouter",
    }
    for env_key, name in env_providers.items():
        if os.getenv(env_key):
            _ensure_provider(name, api_key=os.getenv(env_key))

    # 3. Create default agent if missing
    _ensure_default_agent()
```

### Phase 5: Enterprise Hardening

**E1. Per-user rate limiting**
```python
def check_rate_limit(user):
    settings = frappe.get_single("OwlAI Settings")
    limit = settings.rate_limit_per_minute or 30
    key = f"owlai:rate:{user}"
    count = frappe.cache().get_value(key) or 0
    if count >= limit:
        frappe.throw("Rate limit exceeded. Try again in a minute.")
    frappe.cache().set_value(key, count + 1, expires_in_sec=60)
```

**E2. Health check endpoint**
```python
@frappe.whitelist()
def health_check():
    frappe.only_for("System Manager")
    # Check Ollama connectivity, model availability, tool count, provider status
```

**E3. Remove stale response caching**
The `OwlCache.get(f"response:{conversation.name}", ...)` in router.py returns stale results for dynamic queries. Remove it. Schema and RAG caches are fine.

**E4. Streaming cleanup**
Wrap SSE generator in try/finally with `frappe.db.commit()`.

**E5. Token tracking**
Ollama and OpenAI APIs return token counts. Track actual values in OwlAI Analytics instead of estimating `len(text)/4`.

**E6. Standardize logging**
All `print()` -> `frappe.logger("owlai").info()`. All bare `except:` -> `except Exception as e:` with log.

---

## File Map (After Refactor)

```
tb_owlai_core/
|-- engine/                          # NEW - Core AI engine (zero framework deps)
|   |-- __init__.py
|   |-- llm.py                       # Native LLM client (Ollama + OpenAI-compatible)
|   |-- core.py                      # OwlEngine - agent loop, tool execution
|   +-- conversation.py              # Conversation load/save helpers
|-- api/
|   +-- router.py                    # Cleaned: uses OwlEngine, proper auth
|-- config/
|   |-- __init__.py
|   +-- auto_discovery.py            # Cleaned: lightweight, generic
|-- plugins/
|   |-- base.py                      # BaseTool + BasePlugin (kept)
|   +-- core/
|       |-- plugin.py
|       +-- tools/
|           |-- get_doctype_info.py   # Schema inspection
|           |-- list_documents.py     # List with RBAC
|           |-- get_document.py       # Read with RBAC
|           |-- create_document.py    # Create with RBAC (no ignore_permissions)
|           |-- update_document.py    # Update with RBAC (no ignore_permissions)
|           |-- delete_document.py    # Delete with RBAC
|           |-- search_documents.py   # Search with RBAC
|           |-- navigate.py           # Frontend route change via frappe.set_route()
|           |-- run_doc_method.py     # submit/cancel with method whitelist
|           |-- run_workflow.py       # Workflow transitions
|           +-- frappe_utils.py       # Date/math utilities
|-- utils/
|   |-- __init__.py                  # Cleaned: only check_ollama_status()
|   |-- cache.py                     # Redis cache (kept, MD5->SHA256)
|   +-- context.py                   # OwlContext (cleaned, moved context_builder here)
|-- setup/
|   |-- install.py                   # after_install: full setup
|   +-- setup_defaults.py            # Idempotent provider/agent setup
|-- knowledge/                       # OPTIONAL - RAG (all imports guarded)
|   |-- __init__.py
|   |-- index.py                     # Vector indexing (lancedb optional)
|   +-- search.py                    # Vector search
|-- owlai_core/
|   |-- __init__.py
|   +-- doctype/                     # All DocTypes (kept, Settings cleaned)
|       |-- owlai_settings/
|       |-- owlai_agent/
|       |-- owlai_model/
|       |-- owlai_provider/
|       |-- owlai_tool/
|       |-- owlai_conversation/
|       |-- owlai_message/
|       |-- owlai_analytics/
|       +-- owlai_knowledge_base/
|-- tool_registry.py                 # Cleaned: safe method whitelist, no crewai
|-- hooks.py                         # Cleaned: lightweight after_migrate
|-- tests/
|   |-- test_engine.py               # NEW: test agent loop
|   |-- test_tools.py                # NEW: test each tool + permissions
|   +-- test_api.py                  # NEW: test whitelist endpoints
+-- www/
    +-- owlnest.py                   # Web page context (kept)

DELETED (~40 files, ~4000 lines):
- agno_integrations/          (entire directory - replaced by engine/)
- crewai_integrations/        (entire directory - removed)
- owlai_core/agent.py         (dead code)
- owlai_core/agno_adapter.py  (dead code)
- owlai_core/transcriber.py   (litellm dependency)
- utils/llm_factory.py        (dead code)
- api/crew_api.py             (dead code)
- 22 debug/migration scripts  (dead code)
```

---

## Priority & Effort

| Phase | What | Effort | Impact |
|-------|------|--------|--------|
| **1** | New engine (llm.py + core.py + conversation.py) | 3 days | Removes all hard framework deps |
| **2** | Security hardening (RBAC, ownership, bare excepts) | 2 days | Closes privilege escalation holes |
| **3** | Remove dead code + framework deps | 1 day | -40 files, -4000 lines, clean deps |
| **4** | Make generic (dynamic fields, clean Settings) | 2 days | Works on any Frappe site |
| **5** | Enterprise (rate limit, health check, logging) | 2 days | Production-ready |

**Total: ~10 days for a lean, secure, Frappe-native AI assistant.**

---

## Success Criteria

- [ ] `bench get-app tb_owlai_core && bench install-app tb_owlai_core` on fresh Frappe + Ollama -> works immediately
- [ ] Zero Python packages beyond `requests` + `pydantic` required (both already in Frappe)
- [ ] A "Sales User" role can ONLY query/create Sales-related DocTypes via OwlAI
- [ ] System Manager can add cloud LLM providers as fallback via DocType UI
- [ ] All 25+ bare `except:` replaced with proper error handling
- [ ] Zero hardcoded DocType names in production code
- [ ] `bench migrate` completes in <3 seconds (tool sync only)
- [ ] Rate limiting prevents API quota exhaustion
- [ ] Health check endpoint validates entire AI stack
- [ ] OwlAI navigates user's browser via `frappe.set_route()` when asked "show me X"
- [ ] OwlAI submits/cancels documents via `run_doc_method` within user's permissions
