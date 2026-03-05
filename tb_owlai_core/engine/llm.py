"""
Native LLM client for Ollama and OpenAI-compatible APIs.
Zero framework dependencies — uses only `requests` (bundled with Frappe).
Optional: llama-cpp-python for direct GGUF inference without Ollama.
"""

import json
import os
import requests
import frappe

# Optional llama-cpp-python — only used if installed
try:
    from llama_cpp import Llama  # noqa: F401
    HAS_LLAMA_CPP = True
except ImportError:
    HAS_LLAMA_CPP = False

# Module-level singleton cache: model_path -> Llama instance
_LLAMA_CPP_INSTANCES: dict = {}

logger = frappe.logger("owlai.llm")


class LLMResponse:
    """Normalized response from any LLM provider."""

    def __init__(self, content=None, tool_calls=None, usage=None):
        self.content = content or ""
        self.tool_calls = tool_calls or []
        self.usage = usage or {}

    @property
    def has_tool_calls(self):
        return bool(self.tool_calls)


class OllamaClient:
    """Direct HTTP client for Ollama's native /api/chat endpoint."""

    def __init__(self, host="http://localhost:11434", model="llama3.2"):
        self.host = host.rstrip("/")
        self.model = model
        self.endpoint = f"{self.host}/api/chat"

    def chat(self, messages, tools=None, stream=False):
        """Non-streaming chat completion. Returns LLMResponse."""
        payload = {
            "model": self.model,
            "messages": self._clean_messages(messages),
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(self.endpoint, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.host}. Is it running?"
            )
        except requests.exceptions.Timeout:
            raise TimeoutError("Ollama request timed out after 120s")

        msg = data.get("message", {})
        content = msg.get("content", "")

        tool_calls = []
        for tc in msg.get("tool_calls", []):
            func = tc.get("function", {})
            tool_calls.append({
                "id": tc.get("id", f"call_{len(tool_calls)}"),
                "name": func.get("name", ""),
                "arguments": func.get("arguments", {}),
            })

        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": (data.get("prompt_eval_count", 0) or 0)
            + (data.get("eval_count", 0) or 0),
        }

        return LLMResponse(content=content, tool_calls=tool_calls, usage=usage)

    def chat_stream(self, messages, tools=None):
        """Streaming chat. Yields dicts with content/tool_calls/done/usage.

        Note: Ollama sends tool_calls in a done=false chunk, then a separate
        done=true chunk with usage stats. We accumulate tool_calls across chunks
        and emit them with the final done=true chunk.
        """
        payload = {
            "model": self.model,
            "messages": self._clean_messages(messages),
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(
                self.endpoint, json=payload, stream=True, timeout=300
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.host}. Is it running?"
            )

        accumulated_tool_calls = []

        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = data.get("message", {})
            content = msg.get("content", "")
            done = data.get("done", False)

            # Ollama sends tool_calls in non-done chunks — accumulate them
            for tc in msg.get("tool_calls", []):
                func = tc.get("function", {})
                accumulated_tool_calls.append({
                    "id": tc.get("id", f"call_{len(accumulated_tool_calls)}"),
                    "name": func.get("name", ""),
                    "arguments": func.get("arguments", {}),
                })

            chunk = {"content": content, "done": done}

            if done:
                chunk["tool_calls"] = accumulated_tool_calls
                chunk["usage"] = {
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": (data.get("prompt_eval_count", 0) or 0)
                    + (data.get("eval_count", 0) or 0),
                }

            yield chunk

    def format_tool_result_message(self, tool_call_id, content):
        """Format a tool result message for Ollama."""
        return {"role": "tool", "content": str(content), "tool_call_id": tool_call_id}

    def format_assistant_tool_call_message(self, content, tool_calls):
        """Format an assistant message containing tool calls for Ollama."""
        formatted_calls = []
        for tc in tool_calls:
            formatted_calls.append({
                "function": {
                    "name": tc["name"],
                    "arguments": tc["arguments"]
                    if isinstance(tc["arguments"], dict)
                    else json.loads(tc["arguments"]),
                }
            })
        return {
            "role": "assistant",
            "content": content or "",
            "tool_calls": formatted_calls,
        }

    def _clean_messages(self, messages):
        """Ensure messages are Ollama-compatible (strip unsupported keys)."""
        cleaned = []
        for msg in messages:
            clean = {"role": msg["role"], "content": msg.get("content", "") or ""}
            if msg.get("tool_calls"):
                clean["tool_calls"] = msg["tool_calls"]
            if msg.get("tool_call_id"):
                clean["tool_call_id"] = msg["tool_call_id"]
            cleaned.append(clean)
        return cleaned


class OpenAIClient:
    """Client for OpenAI-compatible APIs (OpenAI, Groq, OpenRouter, vLLM, etc.)."""

    def __init__(
        self,
        api_base="https://api.openai.com/v1",
        api_key=None,
        model="gpt-4o-mini",
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.endpoint = f"{self.api_base}/chat/completions"

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(self, messages, tools=None, stream=False):
        """Non-streaming chat completion. Returns LLMResponse."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(
                self.endpoint,
                headers=self._headers(),
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Cannot connect to {self.api_base}")
        except requests.exceptions.HTTPError as e:
            error_body = ""
            try:
                error_body = e.response.json().get("error", {}).get("message", "")
            except Exception:
                pass
            raise ConnectionError(
                f"LLM API error ({e.response.status_code}): {error_body or str(e)}"
            )

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content", "") or ""

        tool_calls = []
        for tc in msg.get("tool_calls", []):
            func = tc.get("function", {})
            args = func.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tool_calls.append({
                "id": tc.get("id", f"call_{len(tool_calls)}"),
                "name": func.get("name", ""),
                "arguments": args,
            })

        usage_data = data.get("usage", {})
        usage = {
            "prompt_tokens": usage_data.get("prompt_tokens", 0),
            "completion_tokens": usage_data.get("completion_tokens", 0),
            "total_tokens": usage_data.get("total_tokens", 0),
        }

        return LLMResponse(content=content, tool_calls=tool_calls, usage=usage)

    def chat_stream(self, messages, tools=None):
        """Streaming chat. Yields dicts with content/tool_calls/done/usage."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        resp = requests.post(
            self.endpoint,
            headers=self._headers(),
            json=payload,
            stream=True,
            timeout=300,
        )
        resp.raise_for_status()

        accumulated_tool_calls = {}

        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8") if isinstance(line, bytes) else line
            if not line_str.startswith("data: "):
                continue
            data_str = line_str[6:]
            if data_str.strip() == "[DONE]":
                tool_calls = []
                for idx in sorted(accumulated_tool_calls.keys()):
                    tc = accumulated_tool_calls[idx]
                    args = tc.get("arguments_str", "")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, ValueError):
                            args = {}
                    tool_calls.append({
                        "id": tc.get("id", f"call_{idx}"),
                        "name": tc.get("name", ""),
                        "arguments": args,
                    })
                yield {"content": "", "done": True, "tool_calls": tool_calls, "usage": {}}
                return

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choice = data.get("choices", [{}])[0]
            delta = choice.get("delta", {})
            content = delta.get("content", "") or ""

            # Accumulate tool call deltas
            for tc_delta in delta.get("tool_calls", []):
                idx = tc_delta.get("index", 0)
                if idx not in accumulated_tool_calls:
                    accumulated_tool_calls[idx] = {
                        "id": "",
                        "name": "",
                        "arguments_str": "",
                    }
                if tc_delta.get("id"):
                    accumulated_tool_calls[idx]["id"] = tc_delta["id"]
                func = tc_delta.get("function", {})
                if func.get("name"):
                    accumulated_tool_calls[idx]["name"] = func["name"]
                if func.get("arguments"):
                    accumulated_tool_calls[idx]["arguments_str"] += func["arguments"]

            if content:
                yield {"content": content, "done": False}

    def format_tool_result_message(self, tool_call_id, content):
        """Format a tool result message for OpenAI."""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(content),
        }

    def format_assistant_tool_call_message(self, content, tool_calls):
        """Format an assistant message containing tool calls for OpenAI."""
        formatted_calls = []
        for tc in tool_calls:
            args = tc["arguments"]
            if isinstance(args, dict):
                args = json.dumps(args)
            formatted_calls.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": args,
                },
            })
        return {
            "role": "assistant",
            "content": content or None,
            "tool_calls": formatted_calls,
        }


class LlamaCppClient:
    """Direct GGUF inference via llama-cpp-python (no Ollama required).

    Models are loaded once and cached as module-level singletons because
    loading a GGUF file is expensive (several seconds + significant RAM).

    Install the optional dependency with:
        pip install llama-cpp-python
    """

    # Default directories to search for .gguf files
    _DEFAULT_SEARCH_DIRS = [
        # Frappe site private storage
        None,  # filled in dynamically from frappe.get_site_path()
        os.path.expanduser("~/.cache/owlai/models"),
    ]

    def __init__(self, model_path: str):
        if not HAS_LLAMA_CPP:
            raise ImportError(
                "llama-cpp-python is not installed. "
                "Run: pip install llama-cpp-python"
            )
        self.model_path = model_path
        self.model = os.path.basename(model_path)
        self._llm = self._load(model_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(model_path: str):
        """Return a cached Llama instance, loading it on first access."""
        if model_path not in _LLAMA_CPP_INSTANCES:
            from llama_cpp import Llama
            logger.info(f"Loading GGUF model from {model_path}")
            _LLAMA_CPP_INSTANCES[model_path] = Llama(
                model_path=model_path,
                n_ctx=8192,
                n_gpu_layers=-1,  # auto-detect GPU layers
                verbose=False,
            )
        return _LLAMA_CPP_INSTANCES[model_path]

    @staticmethod
    def find_gguf_files() -> list:
        """Return a list of .gguf file paths found in the default search dirs."""
        search_dirs = []
        try:
            site_models = os.path.join(frappe.get_site_path("private"), "models")
            search_dirs.append(site_models)
        except Exception:
            pass
        search_dirs.append(os.path.expanduser("~/.cache/owlai/models"))

        found = []
        for d in search_dirs:
            if not d or not os.path.isdir(d):
                continue
            for fname in os.listdir(d):
                if fname.lower().endswith(".gguf"):
                    found.append(os.path.join(d, fname))
        return found

    def _messages_to_llama(self, messages):
        """Pass messages through as-is (llama-cpp-python accepts the same format)."""
        cleaned = []
        for m in messages:
            entry = {"role": m["role"], "content": m.get("content", "") or ""}
            cleaned.append(entry)
        return cleaned

    def _llama_tools_to_schema(self, tools):
        """Convert our tool list to llama-cpp-python's tools format."""
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.get("name", t.get("function", {}).get("name", "")),
                    "description": t.get("description", t.get("function", {}).get("description", "")),
                    "parameters": t.get("parameters", t.get("function", {}).get("parameters", {})),
                },
            }
            for t in tools
        ]

    def _parse_tool_calls(self, raw_tool_calls):
        """Normalise llama-cpp tool_calls into our standard format."""
        result = []
        for i, tc in enumerate(raw_tool_calls or []):
            func = tc.get("function", {})
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    args = {}
            result.append({
                "id": tc.get("id", f"call_{i}"),
                "name": func.get("name", ""),
                "arguments": args,
            })
        return result

    # ------------------------------------------------------------------
    # Public interface (mirrors OllamaClient / OpenAIClient)
    # ------------------------------------------------------------------

    def chat(self, messages, tools=None, stream=False):
        """Non-streaming chat completion. Returns LLMResponse."""
        kwargs = {
            "messages": self._messages_to_llama(messages),
            "stream": False,
        }
        llama_tools = self._llama_tools_to_schema(tools)
        if llama_tools:
            kwargs["tools"] = llama_tools

        response = self._llm.create_chat_completion(**kwargs)
        choice = response.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content", "") or ""
        tool_calls = self._parse_tool_calls(msg.get("tool_calls"))

        usage_data = response.get("usage", {})
        usage = {
            "prompt_tokens": usage_data.get("prompt_tokens", 0),
            "completion_tokens": usage_data.get("completion_tokens", 0),
            "total_tokens": usage_data.get("total_tokens", 0),
        }
        return LLMResponse(content=content, tool_calls=tool_calls, usage=usage)

    def chat_stream(self, messages, tools=None):
        """Streaming chat. Yields dicts with content/tool_calls/done/usage."""
        kwargs = {
            "messages": self._messages_to_llama(messages),
            "stream": True,
        }
        llama_tools = self._llama_tools_to_schema(tools)
        if llama_tools:
            kwargs["tools"] = llama_tools

        accumulated_tool_calls = []

        for chunk in self._llm.create_chat_completion(**kwargs):
            choice = chunk.get("choices", [{}])[0]
            delta = choice.get("delta", {})
            content = delta.get("content", "") or ""
            finish_reason = choice.get("finish_reason")

            for tc in delta.get("tool_calls", []):
                func = tc.get("function", {})
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, ValueError):
                        args = {}
                accumulated_tool_calls.append({
                    "id": tc.get("id", f"call_{len(accumulated_tool_calls)}"),
                    "name": func.get("name", ""),
                    "arguments": args,
                })

            done = finish_reason is not None
            out = {"content": content, "done": done}
            if done:
                out["tool_calls"] = accumulated_tool_calls
                out["usage"] = chunk.get("usage", {})
            yield out

    def embed(self, text: str) -> list:
        """Return an embedding vector for text (requires embedding-capable model)."""
        result = self._llm.create_embedding(text)
        data = result.get("data", [{}])
        return data[0].get("embedding", []) if data else []

    def format_tool_result_message(self, tool_call_id, content):
        return {"role": "tool", "content": str(content), "tool_call_id": tool_call_id}

    def format_assistant_tool_call_message(self, content, tool_calls):
        formatted = []
        for tc in tool_calls:
            args = tc["arguments"]
            if isinstance(args, dict):
                args = json.dumps(args)
            formatted.append({
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": args},
            })
        return {"role": "assistant", "content": content or "", "tool_calls": formatted}


class NoOpClient:
    """Fallback client when no LLM provider is configured.

    Returns a helpful setup message instead of raising an error, so the
    chat UI degrades gracefully rather than showing a 500 error.
    """

    model = "none"
    _MSG = (
        "No LLM provider configured. "
        "Install Ollama (https://ollama.com) or configure a provider in OwlAI Settings."
    )

    def chat(self, messages, tools=None, stream=False):
        return LLMResponse(content=self._MSG)

    def chat_stream(self, messages, tools=None):
        yield {"content": self._MSG, "done": True, "tool_calls": [], "usage": {}}

    def format_tool_result_message(self, tool_call_id, content):
        return {"role": "tool", "content": str(content), "tool_call_id": tool_call_id}

    def format_assistant_tool_call_message(self, content, tool_calls):
        return {"role": "assistant", "content": content or "", "tool_calls": []}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

DEFAULT_API_BASES = {
    "OpenAI": "https://api.openai.com/v1",
    "Groq": "https://api.groq.com/openai/v1",
    "OpenRouter": "https://openrouter.ai/api/v1",
    "Google Gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}

ENV_KEY_MAP = [
    ("GROQ_API_KEY", "Groq", "https://api.groq.com/openai/v1"),
    ("OPENAI_API_KEY", "OpenAI", "https://api.openai.com/v1"),
    ("OPEN_ROUTER_API_KEY", "OpenRouter", "https://openrouter.ai/api/v1"),
]


def _param_size_gb(model_info):
    """Extract parameter size in billions from Ollama model info."""
    try:
        size_str = model_info.get("details", {}).get("parameter_size", "0B")
        return float(size_str.replace("B", "").replace("M", "e-3").replace("K", "e-6"))
    except (ValueError, TypeError):
        return 0


def get_client(model_doc_name=None):
    """Create the right LLM client. Auto-detects best available provider.

    Priority:
    1. Explicit model_doc_name -> its Provider
    2. OwlAI Settings.default_model -> its Provider
    3. Default OwlAI Provider (is_default=1)
    4. Ollama on localhost (zero-config)
    5. Environment variable API keys
    """
    # 1. Explicit model — but prefer FC-capable if this one can't do tool calls
    if model_doc_name and frappe.db.exists("OwlAI Model", model_doc_name):
        model_doc = frappe.get_doc("OwlAI Model", model_doc_name)
        if model_doc.supports_function_calling:
            provider_doc = frappe.get_doc("OwlAI Provider", model_doc.provider)
            return _client_from_provider(provider_doc, model_doc.model_name)
        else:
            # Explicit model can't do FC — try to find one that can
            logger.warning(
                f"Model '{model_doc_name}' does not support function calling, searching for alternative"
            )
            fc_model = frappe.db.get_value(
                "OwlAI Model",
                {"supports_function_calling": 1},
                ["name", "model_name", "provider"],
                as_dict=True,
            )
            if fc_model:
                provider_doc = frappe.get_doc("OwlAI Provider", fc_model.provider)
                return _client_from_provider(provider_doc, fc_model.model_name)
            # No FC model in DB — fall through to auto-detect

    # 2. Settings default model (prefer function-calling capable)
    try:
        settings = frappe.get_single("OwlAI Settings")
        if settings.default_model and frappe.db.exists(
            "OwlAI Model", settings.default_model
        ):
            model_doc = frappe.get_doc("OwlAI Model", settings.default_model)
            if model_doc.supports_function_calling:
                provider_doc = frappe.get_doc("OwlAI Provider", model_doc.provider)
                return _client_from_provider(provider_doc, model_doc.model_name)
            else:
                # Default model doesn't support FC — try to find one that does
                fc_model = frappe.db.get_value(
                    "OwlAI Model",
                    {"supports_function_calling": 1},
                    ["name", "model_name", "provider"],
                    as_dict=True,
                )
                if fc_model:
                    provider_doc = frappe.get_doc("OwlAI Provider", fc_model.provider)
                    return _client_from_provider(provider_doc, fc_model.model_name)
                # No FC model configured — fall through to auto-detect
    except Exception:
        pass

    # 3. Default provider
    default_provider = frappe.db.get_value(
        "OwlAI Provider", {"is_default": 1}, "name"
    )
    if default_provider:
        provider_doc = frappe.get_doc("OwlAI Provider", default_provider)
        model_name = frappe.db.get_value(
            "OwlAI Model",
            {"provider": default_provider, "supports_function_calling": 1},
            "model_name",
        )
        if not model_name:
            model_name = frappe.db.get_value(
                "OwlAI Model", {"provider": default_provider}, "model_name"
            )
        if model_name:
            return _client_from_provider(provider_doc, model_name)

    # 4. Try Ollama at localhost (zero-config, prefer FC-capable models)
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        resp = requests.get(f"{ollama_host}/api/tags", timeout=2)
        if resp.ok:
            models = resp.json().get("models", [])
            if not models:
                return OllamaClient(host=ollama_host, model="llama3.2")

            # Prefer models known to support function calling (7B+)
            fc_families = {"llama", "qwen2", "mistral", "gemma2", "command-r"}
            fc_candidates = [
                m for m in models
                if m.get("details", {}).get("family") in fc_families
                and _param_size_gb(m) >= 7
            ]
            if fc_candidates:
                return OllamaClient(host=ollama_host, model=fc_candidates[0]["name"])
            # Fallback to first available
            return OllamaClient(host=ollama_host, model=models[0]["name"])
    except Exception:
        pass

    # 5. llama-cpp-python direct GGUF inference (no Ollama required)
    if HAS_LLAMA_CPP:
        gguf_files = LlamaCppClient.find_gguf_files()
        if gguf_files:
            try:
                return LlamaCppClient(model_path=gguf_files[0])
            except Exception as e:
                logger.warning(f"LlamaCppClient init failed: {e}")

    # 6. Environment variable fallback
    for env_key, _name, api_base in ENV_KEY_MAP:
        api_key = os.getenv(env_key)
        if api_key:
            return OpenAIClient(api_base=api_base, api_key=api_key, model="auto")

    return NoOpClient()


def _client_from_provider(provider_doc, model_name):
    """Create a client from an OwlAI Provider DocType record."""
    name = provider_doc.provider_name
    api_base = provider_doc.api_base

    if name == "Ollama":
        # Ollama doesn't need an API key — skip get_password to avoid
        # frappe.throw("Password not found") which kills streaming responses
        host = api_base or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        return OllamaClient(host=host, model=model_name)

    # OpenAI-compatible providers need an API key
    api_key = None
    try:
        api_key = provider_doc.get_password("api_key")
    except Exception:
        pass

    base = api_base or DEFAULT_API_BASES.get(name, "https://api.openai.com/v1")
    return OpenAIClient(api_base=base, api_key=api_key, model=model_name)
