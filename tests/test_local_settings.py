"""LLM settings: the key is only ever READ from the environment / a .env file."""
import inspect
import os
import stat

import pytest

from pvcopilot import config

KEYS = ("PVCOPILOT_API_KEY", "OPENAI_API_KEY", "PVCOPILOT_BASE_URL", "OPENAI_BASE_URL",
        "PVCOPILOT_MODEL", "PVCOPILOT_ENV_FILE", "PVCOPILOT_KEY_VAR", "MY_KEY")


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PVCOPILOT_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.chdir(tmp_path)
    for v in KEYS:
        monkeypatch.delenv(v, raising=False)
    config.reset()
    yield tmp_path
    config.reset()


def test_no_way_to_pass_a_key_directly():
    import pvcopilot
    for fn in (config.configure, pvcopilot.analyze, pvcopilot.run_app):
        assert "api_key" not in inspect.signature(fn).parameters


def test_key_from_chosen_env_file_and_variable(clean_env):
    env = clean_env / "secrets.env"
    env.write_text('CBORG_API_KEY="“sk-cborg-1234567890”"\nOTHER=1\n')
    assert not config.get_config().enabled
    config.configure(env_file=str(env), key_var="CBORG_API_KEY",
                     base_url="https://api.cborg.lbl.gov", model="openai/gpt-5.4-mini")
    c = config.get_config()
    assert c.api_key == "sk-cborg-1234567890"            # quotes stripped
    assert c.source == f"CBORG_API_KEY in {env}"
    assert [n for n, k in config.env_file_variables(env) if k] == ["CBORG_API_KEY"]
    with pytest.raises(FileNotFoundError):
        config.configure(env_file=str(clean_env / "missing.env"))


def test_nothing_is_picked_up_automatically(clean_env, monkeypatch):
    (clean_env / ".env").write_text("OPENAI_API_KEY=sk-local-dotenv-0000\n")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-1111111111")
    monkeypatch.setenv("PVCOPILOT_API_KEY", "sk-env-2222222222")
    c = config.get_config()
    assert c.api_key is None and not c.enabled
    with pytest.raises(ValueError):                 # both pieces are required
        config.configure(env_file=str(clean_env / ".env"))
    with pytest.raises(KeyError):                   # the variable must exist in the file
        config.configure(env_file=str(clean_env / ".env"), key_var="NOPE")


def test_remembered_choices_only_prefill(clean_env):
    env = clean_env / "k.env"
    env.write_text("MY_KEY=sk-secret-abcdef123456\n")
    config.configure(env_file=str(env), key_var="MY_KEY", model="m1")
    p = config.save_settings(**config.current_settings())
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
    text = p.read_text()
    assert "sk-secret" not in text and "MY_KEY" in text
    config.reset()                                  # next session: not applied by itself
    assert config.get_config().api_key is None
    assert config.remembered_settings()["key_var"] == "MY_KEY"
    assert config.clear_saved_settings()


def test_app_has_offline_bar_and_no_key_input():
    from pvcopilot.app import create_app
    app = create_app()
    assert app.server.test_client().get("/").status_code == 200
    layout = str(app.layout)
    for needle in ("LOCAL · OFFLINE", "pvc-local-envfile", "pvc-local-keyvar",
                   "What is sent", "pvc-local-aiswitch"):
        assert needle in layout
    assert "type='password'" not in layout and "pvc-local-key'" not in layout


def test_ai_switch_blocks_every_llm_call(clean_env):
    from pvcopilot import llm
    env = clean_env / "k.env"
    env.write_text("OPENAI_API_KEY=sk-would-be-used-123456\n")
    config.configure(env_file=str(env), key_var="OPENAI_API_KEY")
    try:
        config.set_ai(False)
        assert config.get_config().has_credentials and not llm.is_configured()
        with pytest.raises(llm.LLMNotConfigured):
            llm.get_client()
        config.set_ai(True)
        assert llm.is_configured()
    finally:
        config.set_ai(True)


def test_works_without_a_usable_xgboost():
    """macOS without libomp: importing xgboost fails; PV-Copilot must still run."""
    import subprocess
    import sys
    code = ("import sys; sys.modules['xgboost'] = None\n"      # makes 'import xgboost' fail
            "import pvcopilot\n"
            "r = pvcopilot.analyze('pvdaq4', pvcopilot.EXAMPLE_MAPPINGS['pvdaq4'])\n"
            "assert r.rate is not None and sys.modules['xgboost'].__pvcopilot_stub__\n"
            "print('ok', r.rate)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
