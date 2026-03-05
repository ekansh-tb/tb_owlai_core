"""
OwlAI Model Manager — Zero-config GGUF model auto-download and ONNX embeddings fallback.

Provides:
- ensure_model_available(): downloads a default GGUF if Ollama and local GGUFs are absent
- embed_text_onnx(): FastEmbed-based embedding fallback when Ollama is unavailable

Both features are fully optional. If their dependencies are not installed the
functions return gracefully and the system continues with Ollama.
"""

import os
import frappe

logger = frappe.logger("owlai.model_manager")

# Module-level singleton for FastEmbed model (expensive to load)
_FASTEMBED_MODEL = None

# Default GGUF model to download if nothing is available.
# Small quantised Mistral 7B — good FC support, ~4 GB download.
DEFAULT_GGUF_URL = (
    "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF"
    "/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
)
DEFAULT_GGUF_FILENAME = "mistral-7b-instruct-v0.2.Q4_K_M.gguf"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ensure_model_available(model_name=None):
    """Ensure at least one inference model is available.

    Check order:
    1. Ollama is running and has models → nothing to do.
    2. A .gguf file already exists in the local model dirs → nothing to do.
    3. Neither → download the configured default GGUF into the site's private/models/.

    This function is safe to call from after_install via frappe.enqueue().
    Progress is reported via frappe.publish_realtime().
    """
    import requests

    # 1. Ollama already has models?
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        resp = requests.get(f"{ollama_host}/api/tags", timeout=3)
        if resp.ok and resp.json().get("models"):
            logger.info("OwlAI ModelManager: Ollama is available — skipping model download.")
            return {"status": "ollama_available"}
    except Exception:
        pass

    # 2. Local GGUF files already present?
    from tb_owlai_core.engine.llm import LlamaCppClient
    existing = LlamaCppClient.find_gguf_files()
    if existing:
        logger.info(f"OwlAI ModelManager: Found existing GGUF: {existing[0]}")
        return {"status": "gguf_found", "path": existing[0]}

    # 3. Download default GGUF
    try:
        url, filename = _get_download_config(model_name)
        dest_dir = _ensure_model_dir()
        dest_path = os.path.join(dest_dir, filename)

        if os.path.exists(dest_path):
            logger.info(f"OwlAI ModelManager: Model already downloaded at {dest_path}")
            return {"status": "already_downloaded", "path": dest_path}

        logger.info(f"OwlAI ModelManager: Downloading {filename} from {url}")
        _publish_progress("Downloading OwlAI model (this may take a few minutes)...")

        _download_with_progress(url, dest_path)

        _publish_progress(f"Model downloaded: {filename}")
        logger.info(f"OwlAI ModelManager: Model saved to {dest_path}")
        return {"status": "downloaded", "path": dest_path}

    except Exception as e:
        frappe.log_error(f"OwlAI model download failed: {e}", title="OwlAI Model Manager")
        return {"status": "error", "error": str(e)}


def embed_text_onnx(text: str):
    """Embed text using FastEmbed (ONNX, CPU-only) as a fallback.

    Returns a list of floats on success, or None if FastEmbed is not installed
    or the embedding fails. Caller should fall back to Ollama or return [].

    Install the optional dependency with:
        pip install fastembed
    """
    global _FASTEMBED_MODEL

    try:
        from fastembed import TextEmbedding  # noqa: F401
    except ImportError:
        return None

    try:
        if _FASTEMBED_MODEL is None:
            logger.info("OwlAI ModelManager: Loading FastEmbed BAAI/bge-small-en-v1.5")
            from fastembed import TextEmbedding
            _FASTEMBED_MODEL = TextEmbedding("BAAI/bge-small-en-v1.5")

        embeddings = list(_FASTEMBED_MODEL.embed([text]))
        if embeddings:
            vec = embeddings[0]
            # fastembed returns numpy arrays — convert to plain list
            return vec.tolist() if hasattr(vec, "tolist") else list(vec)
        return None

    except Exception as e:
        logger.error(f"OwlAI FastEmbed error: {e}")
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_download_config(model_name=None):
    """Return (url, filename) for the GGUF to download."""
    url = DEFAULT_GGUF_URL
    filename = DEFAULT_GGUF_FILENAME

    try:
        settings = frappe.get_single("OwlAI Settings")
        configured_url = getattr(settings, "default_gguf_url", None)
        if configured_url:
            url = configured_url
            filename = url.split("/")[-1] or filename
    except Exception:
        pass

    if model_name:
        # Treat model_name as a filename hint if it ends with .gguf
        if model_name.endswith(".gguf"):
            filename = model_name

    return url, filename


def _ensure_model_dir():
    """Create and return the site-local model directory."""
    try:
        site_private = frappe.get_site_path("private")
        model_dir = os.path.join(site_private, "models")
    except Exception:
        model_dir = os.path.expanduser("~/.cache/owlai/models")

    os.makedirs(model_dir, exist_ok=True)
    return model_dir


def _publish_progress(message: str):
    """Emit a realtime progress event to the Frappe desk."""
    try:
        frappe.publish_realtime(
            "owlai_setup_progress",
            {"step": message},
            user=frappe.session.user if hasattr(frappe, "session") else None,
        )
    except Exception:
        pass


def _download_with_progress(url: str, dest_path: str):
    """Download url to dest_path using urllib, reporting progress via frappe.publish_progress."""
    import urllib.request

    tmp_path = dest_path + ".part"

    def _reporthook(block_num, block_size, total_size):
        if total_size <= 0:
            return
        downloaded = block_num * block_size
        pct = min(int(downloaded * 100 / total_size), 100)
        # Publish every 5% to avoid flooding
        if pct % 5 == 0:
            try:
                frappe.publish_progress(
                    pct,
                    title="OwlAI Model Download",
                    description=f"Downloading model... {pct}%",
                )
            except Exception:
                pass

    try:
        urllib.request.urlretrieve(url, tmp_path, reporthook=_reporthook)
        os.replace(tmp_path, dest_path)
    except Exception:
        # Clean up partial download
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
