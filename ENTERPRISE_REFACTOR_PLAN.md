# OwlAI Core - Enterprise Refactor Plan

## Executive Summary

OwlAI Core is a Frappe app providing an AI intelligence layer (chat, agents, RAG, multi-agent crews) for ERPNext. After a thorough review of all ~80 Python files, here is a prioritized plan to make it **enterprise-grade, production-ready, and generic for any Frappe/ERPNext environment**.

---

## Phase 1: CRITICAL BUG FIXES & SECURITY (P0)

### 1.1 Eliminate `ignore_permissions=True` Abuse
**Files:** `frappe_crud.py`, `create_document.py`, `storage.py`, `router.py`, `tool_registry.py`, `auto_discovery.py`

- `frappe_crud.py:49,59,65` — Insert/update/delete all bypass permissions. The AI agent can delete any document as any user.
- `create_document.py:139` — Checks `has_permission("create")` but then calls `insert(ignore_permissions=True)`, defeating the check.
- `storage.py:38,164,185,219` — Conversation/memory operations bypass permissions.

**Fix:** Replace `ignore_permissions=True` with proper permission-aware calls. Use `frappe.session.user` context. Only bypass for system-internal operations (tool sync, auto-discovery) — never for user-facing CRUD.

### 1.2 Fix Arbitrary Code Execution Path
**File:** `tool_registry.py:122`

```python
res = frappe.call(tool_doc.method_path, **arguments)
```

This executes any dotted path stored in the DB with user-controlled arguments. A compromised or malicious `OwlAI Tool` record could call any Frappe method.

**Fix:** Maintain a strict whitelist of allowed method paths. Validate against it before calling.

### 1.3 Fix Bare `except:` Clauses (25+ instances)
**Files:** `storage.py` (5), `router.py` (7), `tools.py` (4), `tool_registry.py` (1), `context_builder.py` (1), `auto_seed.py` (3), `context.py` (1), `setup_defaults.py` (1), `get_doctype_info.py` (1)

These silently swallow all exceptions including `SystemExit`, `KeyboardInterrupt`, and `MemoryError`. Critical bugs are invisible.

**Fix:** Replace every bare `except:` with `except Exception as e:` and log/handle appropriately.

### 1.4 Fix SQL Injection Vector
**File:** `knowledge_index.py:175`

```python
vector_db.delete(where=f"doc_name = '{doc_name}'")
```

String-interpolated SQL filter. If `doc_name` contains a single quote, it breaks or injects.

**Fix:** Use parameterized queries or the vector DB's native safe filtering.

### 1.5 Validate `@frappe.whitelist()` Endpoints
**File:** `router.py` — All 10+ whitelisted endpoints

- `handle_stream_input` and `handle_input_v2` accept a `conversation_id` but don't verify the user owns that conversation before proceeding.
- `delete_conversation` doesn't check ownership.
- `update_owlai_settings` doesn't check if the user is System Manager.

**Fix:** Add explicit permission checks at the start of every whitelisted method.

---

## Phase 2: ARCHITECTURAL CLEANUP (P1)

### 2.1 Eliminate Dual Agent Architecture
**Problem:** Two parallel agent systems exist:
1. `owlai_core/agent.py` → `OwlAgent` (uses manual history, LiteLLM, has unfinished image/audio handling)
2. `agno_integrations/main.py` → `get_agent()` (uses Agno storage, memory, compression)

`router.py` only uses path 2. `OwlAgent` (path 1) is dead code referenced nowhere in production flow.

**Fix:** Delete `owlai_core/agent.py` and `owlai_core/agno_adapter.py`. Consolidate on the Agno-based agent in `agno_integrations/main.py`.

### 2.2 Eliminate Dual LLM Factory
**Problem:** Two model factory systems:
1. `utils/llm_factory.py` — LangChain-based (`ChatOpenAI`, `ChatOllama`, etc.)
2. `agno_integrations/model_factory.py` — Agno-based (`Ollama`, `OpenAIChat`, etc.)

LangChain factory is only imported by `utils/__init__.py` (legacy `get_active_provider_config`) and never used in the active agent flow.

**Fix:** Delete `utils/llm_factory.py`. Remove `langchain-*` dependencies from `requirements.txt`. Keep `agno_integrations/model_factory.py` as the single source.

### 2.3 Eliminate Dual Toolkit System
**Problem:** Two toolkit implementations:
1. `owlai_core/agno_adapter.py` → `OwlAIToolkit` — wraps plugin tools for Agno
2. `agno_integrations/tools.py` → `FrappeToolkit` — standalone Agno toolkit with hardcoded methods

The active flow uses `FrappeToolkit` which duplicates the plugin tool's logic directly as methods, making the plugin system partially redundant.

**Fix:** Merge into one toolkit. `FrappeToolkit` should delegate to `ToolRegistry` for ALL operations (it already does for some via `_exec`). Remove `OwlAIToolkit`.

### 2.4 Remove Dead Scripts and Debug Files
**Files to delete (not imported or used in production):**
- `agno_check.py`, `check_agents.py`, `check_rag.py`, `check_rag_deep.py`
- `debug_config.py`, `debug_discovery.py`, `debug_owlai.py`
- `dump_agent_config.py`, `fix_config.py`, `force_register_tools.py`
- `import_opening_balances.py`, `investigate_entities.py`
- `register_crud.py`, `register_run_crew.py`, `reindex_failed.py`
- `setup_partners_assets.py`, `sync_tools.py`, `test_agent.py`
- `update_agent_tools.py`, `verify_agents.py`, `verify_agno_install.py`, `verify_crud.py`

These are one-off debugging and migration scripts cluttering the package.

### 2.5 Clean Up `utils/__init__.py`
**Problem:** Contains legacy `get_active_provider_config()` which references old Settings fields (`gemini_api_key`, `gemini_model`, `ollama_url`) and imports `litellm`/`requests`. This is dead code in the Agno flow.

**Fix:** Remove the function. Move `check_ollama_status` to `utils/ollama_utils.py` where it belongs.

---

## Phase 3: HARDCODED VALUE REMOVAL (P1)

### 3.1 Remove Hardcoded Model Names
**Files:** `auto_discovery.py`, `model_factory.py`, `setup_defaults.py`

- `"llama3-70b-8192"`, `"claude-3-5-sonnet-20240620"`, `"gpt-4o"`, `"llama3.2:3b"` hardcoded as defaults
- `"google/gemini-2.0-flash-001"` hardcoded for OpenRouter
- `"nomic-embed-text"` hardcoded for embeddings in `knowledge_index.py`

**Fix:** Move all model defaults to `OwlAI Settings` DocType fields with sensible defaults. Allow admin override without code changes.

### 3.2 Remove Hardcoded URLs
- `"http://localhost:11434"` appears in 5+ files
- `"https://openrouter.ai/api/v1"` in 2 files

**Fix:** Single source: `OwlAI Settings` or `OwlAI Provider.api_base`.

### 3.3 Remove Hardcoded DocType Lists
**File:** `tools.py:150-153` — Smart fields per DocType:
```python
if doctype == "Sales Order": parsed_fields = ["name", "customer", "grand_total", "status"]
elif doctype == "Task": parsed_fields = ["name", "subject", "status", "priority", "exp_end_date"]
```

**File:** `context_builder.py:135-141` — Hardcoded common DocTypes list.

**File:** `router.py:407` — Hardcoded common DocTypes for introspection.

**Fix:** Use `frappe.get_meta(doctype)` to dynamically pick title/name/status fields. Remove all ERPNext-specific assumptions.

### 3.4 Remove "TechBirdIt" Branding
**Files:** `hooks.py`, `pyproject.toml`

For a generic app, the publisher/email should be configurable or generic. App should work for any Frappe site regardless of who built it.

---

## Phase 4: ROBUSTNESS & ERROR HANDLING (P1)

### 4.1 Fix Global Mutable State Pattern
**Problem:** `frappe.local.owlai_actions` is used as a side-channel queue between tools and the router. Tools append actions, router reads and clears them.

**Risk:** Race conditions in concurrent requests. If two users chat simultaneously, their actions could leak.

**Fix:** Pass an `ActionCollector` object through the tool execution context instead of using `frappe.local`.

### 4.2 Fix Streaming Cleanup
**File:** `router.py:213-297`

The SSE generator captures errors but doesn't guarantee DB commit or connection cleanup if the client disconnects mid-stream.

**Fix:** Add `try/finally` with `frappe.db.commit()` in generator. Consider using `frappe.enqueue` for heavy processing.

### 4.3 Fix Response Caching Logic
**File:** `router.py:378-381`

```python
cached_response = OwlCache.get(f"response:{conversation.name}", cache_payload)
if cached_response:
    return cached_response
```

Same conversation + same text = cached response even if the underlying data changed. This is wrong for dynamic queries ("What's the latest Sales Order?").

**Fix:** Remove response caching, or only cache for truly idempotent queries. The RAG and schema caches are fine.

### 4.4 Fix MD5 in Cache Keys
**File:** `cache.py:19`

```python
hash_val = hashlib.md5(data_str.encode()).hexdigest()
```

MD5 is collision-prone (not a security issue here, but bad practice).

**Fix:** Use `hashlib.sha256` or `xxhash` for speed.

---

## Phase 5: ENTERPRISE FEATURES (P2)

### 5.1 Add Rate Limiting
No rate limiting on chat endpoints. A single user could spam requests and exhaust LLM API quotas/budgets.

**Fix:** Add per-user rate limiting in `handle_stream_input` and `handle_input_v2` using Frappe Redis cache. Configurable in `OwlAI Settings` (e.g., 30 requests/minute).

### 5.2 Add Token/Cost Budget Controls
No guardrails on LLM spend. `completion_tokens` is estimated as `len(text)/4` in the streaming path.

**Fix:**
- Add `monthly_token_budget` field to `OwlAI Settings`
- Track actual token usage in `OwlAI Analytics`
- Reject requests when budget exceeded
- Calculate actual tokens from model response metrics

### 5.3 Add Proper Audit Trail
Current analytics logging is optional and has `except: pass`.

**Fix:**
- Make analytics always-on for enterprise (configurable granularity)
- Log: user, model, tokens, cost, tool calls, duration, IP
- Add retention policy (auto-cleanup old records)

### 5.4 Add Multi-Tenancy Support
**Problem:** `auto_discovery.py:64` hardcodes a single "Owl Assistant" agent for the entire site. No support for different companies/departments having different agents or models.

**Fix:** Support company-level or role-level agent assignment. Agent selection should consider user's default company and roles.

### 5.5 Add Health Check Endpoint
No way to verify the AI stack is healthy (Ollama running? Vector DB indexed? API keys valid?).

**Fix:** Add a `@frappe.whitelist()` health check that validates: provider connectivity, model availability, vector DB status, and returns a status dashboard.

---

## Phase 6: TEST COVERAGE (P2)

### 6.1 Fix Broken Tests
**File:** `tests/test_core_tools.py:13` calls `self.registry.get_available_tools()` — method doesn't exist on `ToolRegistry`.

**Fix:** Update test to use `self.registry.plugin_manager.get_all_tools()`.

### 6.2 Add Missing Tests
Current coverage: 4 test files, most are stubs or broken.

**Needed:**
- Unit tests for each tool in `plugins/core/tools/`
- Integration tests for `FrappeToolkit` methods
- Permission tests (verify non-admin can't delete others' documents)
- API endpoint tests for all `@frappe.whitelist()` methods
- Storage backend tests for `FrappeStorage`
- Model factory tests for each provider path

---

## Phase 7: DEPENDENCY CLEANUP (P2)

### 7.1 Clean `requirements.txt`
Current:
```
litellm, frappe, agno, tantivy, beautifulsoup4, pypdf, crewai, chromadb, lancedb
```

**Issues:**
- `litellm` — Only imported in `router.py:8` but never used (the `completion` import is dead code)
- `chromadb` — Never imported anywhere in the codebase
- `tantivy` — Never directly imported
- `frappe` — Managed by bench, shouldn't be in requirements
- LangChain deps in `llm_factory.py` are not in requirements but imported

**Fix:** Remove `litellm`, `chromadb`, `tantivy`, `frappe`. Make `crewai`, `lancedb`, `beautifulsoup4`, `pypdf` optional extras. Core should only need `agno`.

### 7.2 Add Optional Dependency Guards
Many imports assume packages exist. Some use try/except but many don't.

**Fix:** Consistent pattern for optional deps:
```python
HAS_CREWAI = False
try:
    from crewai import Crew
    HAS_CREWAI = True
except ImportError:
    pass
```

---

## Phase 8: CONFIGURATION & UX POLISH (P3)

### 8.1 Fix `OwlAI Settings` DocType
Has legacy fields (`gemini_api_key`, `gemini_model`, `ollama_url`, `ollama_model`, `provider` as string select) that conflict with the new Provider/Model DocType system.

**Fix:** Deprecate legacy fields. Settings should only reference `default_agent`, `default_model` (Link to OwlAI Model), and feature flags.

### 8.2 Add Proper Logging
Inconsistent logging: some use `frappe.log_error()`, some use `frappe.logger()`, some use `print()`.

**Fix:** Standardize on `frappe.logger("owlai")` with consistent log levels. Remove all `print()` statements.

### 8.3 Add Proper `after_migrate` Hook
Current `after_migrate` calls `discover_and_register_providers()` which does too much (seeds KB, creates agents). This slows every `bench migrate`.

**Fix:** Split into lightweight sync (tools only) and heavy setup (providers, agents, KB). Only do lightweight on migrate.

---

## Implementation Priority

| Phase | Effort | Impact | Risk if Skipped |
|-------|--------|--------|-----------------|
| P0: Security fixes | 2-3 days | Critical | Data breach, privilege escalation |
| P1: Architecture cleanup | 3-4 days | High | Maintenance nightmare, bugs |
| P1: Hardcoded removal | 1-2 days | High | Won't work on non-TechBirdIt sites |
| P1: Error handling | 1-2 days | High | Silent failures in production |
| P2: Enterprise features | 3-5 days | Medium | Not enterprise-ready |
| P2: Tests | 2-3 days | Medium | Regressions on updates |
| P2: Deps cleanup | 1 day | Medium | Bloated installs, conflicts |
| P3: Config/UX | 1-2 days | Low | Confusing admin experience |

**Total estimated effort: ~15-22 days for full enterprise readiness.**
