"""LLM settings for PV-Copilot: nothing is found automatically.

PV-Copilot ships without any API key, never takes a key typed in, and never
goes looking for one: it does NOT read OPENAI_API_KEY from the environment, nor
any .env file on its own. The user explicitly provides

* the path of a ``.env`` file on this computer, and
* the name of the variable in it that holds the key (e.g. ``CBORG_API_KEY``),
* optionally the endpoint (base URL) and the model,

through the web UI's "AI settings" panel, the CLI flags ``--env-file
--key-var --base-url --model``, or ``pvcopilot.configure(...)``. The key is then
read from that file, kept in memory only, and never shown, sent to the browser
or written to disk. Until this is done, no LLM can be called.

A local server such as Ollama needs no key: give only the base URL.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_FAST_MODEL_OPENAI = "gpt-5.4-nano"

_QUOTES = " \t\r\n\"'“”‘’„‟«»`"


def clean(v):
    """Strip whitespace and stray quotes (incl. curly quotes from copy-paste);
    "" -> None."""
    if v is None:
        return None
    v = str(v).strip().strip(_QUOTES)
    if v.lower().startswith("bearer "):
        v = v[7:].strip(_QUOTES)
    return v or None


def _expand(path):
    return str(Path(os.path.expandvars(str(path))).expanduser()) if path else None


def read_env_file(path) -> dict:
    """Variables in a .env file (values are only used in memory)."""
    from dotenv import dotenv_values
    p = _expand(path)
    if not p or not os.path.isfile(p):
        return {}
    return {k: v for k, v in dotenv_values(p).items() if k}


def env_file_variables(path) -> list[tuple[str, bool]]:
    """(name, looks_like_a_key) for every variable in a .env file. Names only."""
    hint = ("KEY", "TOKEN", "SECRET")
    return [(k, any(h in k.upper() for h in hint)) for k in read_env_file(path)]


@dataclass(frozen=True)
class LLMConfig:
    api_key: str | None = None          # resolved value, held in memory only
    base_url: str | None = None
    model: str | None = None
    fast_model: str | None = None
    timeout: float = 60.0
    source: str = ""                    # where the key was read from
    env_file: str | None = None
    key_var: str | None = None
    ai_on: bool = True

    @property
    def is_openai(self):
        return not self.base_url or "api.openai.com" in self.base_url

    @property
    def has_credentials(self):
        """A key was found, or a custom (e.g. local) server is set."""
        return bool(self.api_key or self.base_url)

    @property
    def enabled(self):
        """True when an LLM may be called: AI switched on AND credentials available."""
        return self.ai_on and self.has_credentials

    @property
    def resolved_model(self):
        return self.model or DEFAULT_MODEL

    @property
    def resolved_fast_model(self):
        if self.fast_model:
            return self.fast_model
        if self.model or not self.is_openai:
            return self.resolved_model
        return DEFAULT_FAST_MODEL_OPENAI

    def describe(self):
        if self.api_key:
            key = f"{mask(self.api_key)} from {self.source}"
        elif self.env_file:
            key = f"{self.key_var} is empty in {self.env_file}"
        else:
            key = "not provided (AI settings, or --env-file FILE --key-var NAME)"
        return (f"AI       : {'on' if self.ai_on else 'OFF (no LLM calls)'}\n"
                f"api key  : {key}\n"
                f"endpoint : {self.base_url or 'https://api.openai.com/v1 (default)'}\n"
                f"model    : {self.resolved_model}")


def mask(key):
    if not key:
        return "none"
    return key[:3] + "…" + key[-4:] if len(key) > 12 else "…"


@dataclass(frozen=True)
class _Settings:                     # what the user chooses; nothing secret
    env_file: str | None = None
    key_var: str | None = None
    base_url: str | None = None
    model: str | None = None
    fast_model: str | None = None
    timeout: float | None = None


_override = _Settings()

# The AI master switch. When off, PV-Copilot makes no LLM call at all, whatever
# key is available. The Python API starts with it on (a script that configures a
# key wants it used); the web UI starts with it OFF and the user turns it on.
_ai_on = (clean(os.environ.get("PVCOPILOT_AI")) or "on").lower() not in ("off", "0", "false", "no")


def set_ai(on: bool):
    """Switch every AI feature on or off for this process."""
    global _ai_on
    _ai_on = bool(on)
    from . import llm
    llm.reset_client()
    return get_config()


def ai_is_on() -> bool:
    return _ai_on


def configure(env_file=None, key_var=None, base_url=None, model=None, fast_model=None,
              timeout=None):
    """Choose where the key is read from, and the endpoint / model.

    >>> import pvcopilot
    >>> pvcopilot.configure(env_file="~/keys/pvcopilot.env", key_var="OPENAI_API_KEY")
    >>> pvcopilot.configure(env_file="~/keys/pvcopilot.env", key_var="CBORG_API_KEY",
    ...                     base_url="https://api.cborg.lbl.gov", model="openai/gpt-5.4-mini")
    >>> pvcopilot.configure(base_url="http://localhost:11434/v1", model="qwen3:14b")  # Ollama
    """
    global _override
    kw = {k: clean(v) for k, v in dict(env_file=env_file, key_var=key_var, base_url=base_url,
                                       model=model, fast_model=fast_model).items()
          if v is not None}
    if kw.get("env_file"):
        kw["env_file"] = _expand(kw["env_file"])
        if not os.path.isfile(kw["env_file"]):
            raise FileNotFoundError(f".env file not found: {kw['env_file']}")
    env_file = kw.get("env_file", _override.env_file)
    key_var = kw.get("key_var", _override.key_var)
    if bool(env_file) != bool(key_var):
        raise ValueError("Give both the .env file and the name of the key variable in it.")
    if env_file and key_var not in read_env_file(env_file):
        raise KeyError(f"{key_var} is not defined in {env_file}")
    if timeout is not None:
        kw["timeout"] = timeout
    _override = replace(_override, **kw)
    from . import llm
    llm.reset_client()
    return get_config()


def reset():
    """Forget settings made with configure() in this process."""
    global _override
    _override = _Settings()
    from . import llm
    llm.reset_client()


# ---- optional settings file (non-secret; written when the user ticks "remember") ----
def settings_path():
    import sys
    d = os.environ.get("PVCOPILOT_CONFIG_DIR")
    if not d:
        if sys.platform == "darwin":
            d = Path.home() / "Library" / "Application Support" / "pvcopilot"
        elif os.name == "nt":
            d = Path(os.environ.get("APPDATA", Path.home())) / "pvcopilot"
        else:
            d = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pvcopilot"
    return Path(d) / "settings.json"


_ALLOWED_SAVED = ("env_file", "key_var", "base_url", "model", "fast_model")


def _saved():
    import json
    try:
        d = json.loads(settings_path().read_text(encoding="utf-8"))
        return {k: clean(d.get(k)) for k in _ALLOWED_SAVED if d.get(k)}   # never a key
    except Exception:
        return {}


def save_settings(env_file=None, key_var=None, base_url=None, model=None, fast_model=None):
    """Remember the (non-secret) settings for next time."""
    import json
    p = settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in dict(env_file=env_file, key_var=key_var, base_url=base_url,
                                  model=model, fast_model=fast_model).items() if v}
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, p)
    return p


def clear_saved_settings():
    try:
        settings_path().unlink()
        return True
    except FileNotFoundError:
        return False


def _settings() -> _Settings:
    return _override          # only what the user provided in this session


def get_config() -> LLMConfig:
    s = _settings()
    key, source = None, ""
    if s.env_file and s.key_var:
        key = clean(read_env_file(s.env_file).get(s.key_var))
        source = f"{s.key_var} in {s.env_file}" if key else ""
    return LLMConfig(api_key=key, base_url=s.base_url, model=s.model, fast_model=s.fast_model,
                     timeout=s.timeout or 60.0, source=source,
                     env_file=s.env_file, key_var=s.key_var, ai_on=_ai_on)


def current_settings() -> dict:
    """The user's choices in this session (no key)."""
    s = _settings()
    return {k: getattr(s, k) for k in _ALLOWED_SAVED}


def remembered_settings() -> dict:
    """Choices saved with "remember": only used to PREFILL the settings panel;
    they take effect only when the user clicks Apply."""
    return _saved()
