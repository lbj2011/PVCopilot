"""One shared, lazily-built OpenAI-compatible client.

The analysis and app modules do ``from pvcopilot.llm import client`` and call
``client.chat.completions.create(...)`` exactly as they did with a module-level
``openai.OpenAI(...)``. The real client is only built on first use, from the
settings in :mod:`pvcopilot.config`, so importing PV-Copilot never needs a key.
"""
from __future__ import annotations

import threading

from .config import get_config


class LLMNotConfigured(RuntimeError):
    pass


_NOT_CONFIGURED_MSG = (
    "No API key provided. PV-Copilot never looks for one on its own: tell it which "
    ".env file holds the key and the variable name, e.g.\n"
    "  * web UI:  AI settings -> 1 .env file, 2 key variable -> Apply\n"
    "  * CLI:     pvcopilot ui --env-file ~/keys/pvcopilot.env --key-var OPENAI_API_KEY\n"
    "  * Python:  pvcopilot.configure(env_file='~/keys/pvcopilot.env', key_var='OPENAI_API_KEY')\n"
    "A local model needs no key: give only --base-url http://localhost:11434/v1 --model ...\n"
    "Or skip the LLM: pass mapping={...} to analyze()."
)

_lock = threading.Lock()
_client = None
_client_cfg = None


def reset_client():
    global _client, _client_cfg
    with _lock:
        _client, _client_cfg = None, None


def is_configured() -> bool:
    return get_config().enabled


def get_client():
    """The openai.OpenAI client for the current settings (rebuilt if they changed)."""
    global _client, _client_cfg
    cfg = get_config()
    if not cfg.ai_on:
        raise LLMNotConfigured("AI is switched off (no LLM calls are made).")
    if not cfg.enabled:
        raise LLMNotConfigured(_NOT_CONFIGURED_MSG)
    with _lock:
        if _client is None or _client_cfg != cfg:
            import openai
            _client = openai.OpenAI(
                api_key=cfg.api_key or "not-needed",   # local servers ignore the key
                base_url=cfg.base_url or None,
                timeout=cfg.timeout,
                max_retries=1,      # a wrong key or no network should fail fast
            )
            _client_cfg = cfg
        return _client


def get_model(kind: str = "main") -> str:
    cfg = get_config()
    return cfg.resolved_fast_model if kind == "fast" else cfg.resolved_model


class _ClientProxy:
    """Stands in for an ``openai.OpenAI`` instance; resolves on attribute access."""

    def __getattr__(self, name):
        return getattr(get_client(), name)

    def __bool__(self):
        return is_configured()

    def __repr__(self):
        return f"<pvcopilot LLM client: {'configured' if is_configured() else 'not configured'}>"


client = _ClientProxy()


def redact(text) -> str:
    """Replace the configured key in a message (e.g. a provider error) by its mask."""
    text = str(text)
    key = get_config().api_key
    if key and len(key) > 6:
        from .config import mask
        text = text.replace(key, mask(key))
    return text


def describe_error(e) -> str:
    """Short, user-facing reason for a failed LLM call."""
    name = type(e).__name__
    text = str(e).lower()
    if isinstance(e, UnicodeError) or "ascii" in text:
        return "the API key contains invalid characters, e.g. curly quotes “ ” around it"
    if name == "AuthenticationError" or "401" in text or "invalid api key" in text \
            or "incorrect api key" in text:
        return "the API key was rejected"
    if name == "PermissionDeniedError" or "403" in text:
        return "the key has no access to this model"
    if name == "NotFoundError" or "model_not_found" in text or "does not exist" in text:
        return "model not found at this endpoint"
    if name == "RateLimitError" or "429" in text or "quota" in text:
        return "rate limit or quota exceeded"
    if name in ("APIConnectionError", "APITimeoutError", "ConnectError") or "connect" in text:
        return "could not reach the endpoint (network or base URL)"
    if name == "LLMNotConfigured":
        return "AI is switched off" if "switched off" in text else "no API key configured"
    return name


def chat(messages, kind="main", **kw):
    """Convenience wrapper: one chat completion, returns the text."""
    resp = get_client().chat.completions.create(model=get_model(kind), messages=messages, **kw)
    return resp.choices[0].message.content
