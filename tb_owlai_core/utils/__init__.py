import frappe
import os
import requests


def check_ollama_status(url=None):
    """Ping the Ollama server. Returns True if accessible."""
    url = url or os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        response = requests.get(url, timeout=2)
        return response.status_code == 200
    except Exception:
        return False
