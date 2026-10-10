"""Groq client. The model is configurable and auto-resolved - never hard-coded.

GROQ_MODEL in .env wins. If it is empty, or Groq says the model is gone/decommissioned,
we ask Groq's /models endpoint what is currently available and pick a Llama model.
"""
import time

import requests

from . import config

PREFERRED = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
NOT_CHAT = ("whisper", "guard", "tts", "playai", "orpheus", "embed", "safeguard")

_cache = {"model": None, "ts": 0.0}


class GroqError(Exception):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.status = status


def _headers():
    if not config.GROQ_API_KEY:
        raise GroqError("GROQ_API_KEY is missing. Add it to your .env file.", 401)
    return {"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"}


def list_models():
    r = requests.get(f"{config.GROQ_BASE_URL}/models", headers=_headers(), timeout=20)
    if r.status_code != 200:
        raise GroqError(f"Could not list Groq models ({r.status_code}).", r.status_code)
    ids = [m["id"] for m in r.json().get("data", []) if m.get("active", True)]
    return [i for i in ids if not any(x in i.lower() for x in NOT_CHAT)]


def resolve_model(force=False):
    """Return the model to use: env override, else best available Llama on Groq."""
    if config.GROQ_MODEL and not force:
        return config.GROQ_MODEL
    if _cache["model"] and not force and time.time() - _cache["ts"] < 3600:
        return _cache["model"]
    ids = list_models()
    if not ids:
        raise GroqError("Groq returned no usable chat models for this key.")
    pick = next((m for m in PREFERRED if m in ids), None)
    if not pick:
        llamas = sorted((i for i in ids if "llama" in i.lower()), reverse=True)
        pick = llamas[0] if llamas else ids[0]
    _cache.update(model=pick, ts=time.time())
    print(f"[groq] using model: {pick}")
    return pick


def _post(model, messages, temperature):
    return requests.post(
        f"{config.GROQ_BASE_URL}/chat/completions", headers=_headers(), timeout=60,
        json={"model": model, "messages": messages, "temperature": temperature,
              "max_tokens": config.MAX_TOKENS})


def chat(messages, temperature=0.2):
    model = resolve_model()
    r = _post(model, messages, temperature)
    if r.status_code in (400, 404) and ("model" in r.text.lower()):
        # configured model removed/decommissioned -> pick a currently available one
        model = resolve_model(force=True)
        r = _post(model, messages, temperature)
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", r.text)
        except ValueError:
            msg = r.text
        raise GroqError(msg, r.status_code)
    return r.json()["choices"][0]["message"]["content"].strip()
