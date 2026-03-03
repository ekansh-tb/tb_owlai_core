"""
Native LLM client for Ollama and OpenAI-compatible APIs.
Zero framework dependencies — uses only `requests` (bundled with Frappe).
"""

import json
import os
import requests
import frappe

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
        """Streaming chat. Yields dicts with content/tool_calls/done/usage."""
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

            chunk = {"content": content, "done": done}

            if done:
                tool_calls = []
                for tc in msg.get("tool_calls", []):
                    func = tc.get("function", {})
                    tool_calls.append({
                        "id": tc.get("id", f"call_{len(tool_calls)}"),
                        "name": func.get("name", ""),
                        "arguments": func.get("arguments", {}),
                    })
                chunk["tool_calls"] = tool_calls
                chunk["usage"] = {
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": (data.get("prompt_eval_count", 0) or 0)
                    + (data.get("eval_count", 0) or 0),
                }

            yield chunk

    def format_tool_result_message(self, tool_call_id, content):
        """Format a tool result message for Ollama."""
        return {"role": "tool", "content": str(content)}

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


def get_client(model_doc_name=None):
    """Create the right LLM client. Auto-detects best available provider.

    Priority:
    1. Explicit model_doc_name -> its Provider
    2. OwlAI Settings.default_model -> its Provider
    3. Default OwlAI Provider (is_default=1)
    4. Ollama on localhost (zero-config)
    5. Environment variable API keys
    """
    # 1. Explicit model
    if model_doc_name and frappe.db.exists("OwlAI Model", model_doc_name):
        model_doc = frappe.get_doc("OwlAI Model", model_doc_name)
        provider_doc = frappe.get_doc("OwlAI Provider", model_doc.provider)
        return _client_from_provider(provider_doc, model_doc.model_name)

    # 2. Settings default model
    try:
        settings = frappe.get_single("OwlAI Settings")
        if settings.default_model and frappe.db.exists(
            "OwlAI Model", settings.default_model
        ):
            model_doc = frappe.get_doc("OwlAI Model", settings.default_model)
            provider_doc = frappe.get_doc("OwlAI Provider", model_doc.provider)
            return _client_from_provider(provider_doc, model_doc.model_name)
    except Exception:
        pass

    # 3. Default provider
    default_provider = frappe.db.get_value(
        "OwlAI Provider", {"is_default": 1}, "name"
    )
    if default_provider:
        provider_doc = frappe.get_doc("OwlAI Provider", default_provider)
        model_name = frappe.db.get_value(
            "OwlAI Model", {"provider": default_provider}, "model_name"
        )
        if model_name:
            return _client_from_provider(provider_doc, model_name)

    # 4. Try Ollama at localhost (zero-config)
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        resp = requests.get(f"{ollama_host}/api/tags", timeout=2)
        if resp.ok:
            models = resp.json().get("models", [])
            model = models[0]["name"] if models else "llama3.2"
            return OllamaClient(host=ollama_host, model=model)
    except Exception:
        pass

    # 5. Environment variable fallback
    for env_key, _name, api_base in ENV_KEY_MAP:
        api_key = os.getenv(env_key)
        if api_key:
            return OpenAIClient(api_base=api_base, api_key=api_key, model="auto")

    raise ConnectionError(
        "No LLM provider available. "
        "Install Ollama (https://ollama.com) or configure a provider in OwlAI Settings."
    )


def _client_from_provider(provider_doc, model_name):
    """Create a client from an OwlAI Provider DocType record."""
    name = provider_doc.provider_name
    api_base = provider_doc.api_base

    try:
        api_key = provider_doc.get_password("api_key")
    except Exception:
        api_key = None

    if name == "Ollama":
        host = api_base or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        return OllamaClient(host=host, model=model_name)

    # OpenAI-compatible providers
    base = api_base or DEFAULT_API_BASES.get(name, "https://api.openai.com/v1")
    return OpenAIClient(api_base=base, api_key=api_key, model=model_name)
