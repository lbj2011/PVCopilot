"""pvcopilot.analyze() must give the web app's Simple-mode rate on every example.

The app path runs the real Dash callbacks (simple_stage_data -> _filter -> _calc)
from pvcopilot.app.page. The LLM is replaced by fixed column candidates (the
same hook for both paths), so this runs offline and with no API key.

    pytest tests/test_matches_app.py -q        (about 1-2 min)
"""
import pytest

import pvcopilot
from pvcopilot.core import analysis_utils as AU
from pvcopilot.examples import EXAMPLES

from pvcopilot.examples import EXAMPLE_MAPPINGS as MAPPINGS


def _auto_choice(name):
    """The columns the app picks itself where it overrides the given candidates."""
    return {"nrel_stf": {"Irradiance": "poa_local"}}.get(name, {})


def _app_rate(name, monkeypatch):
    from pvcopilot.app import page as P
    from pvcopilot.pipeline import _mapping_to_candidates
    df = pvcopilot.load_example(name)
    cand = _mapping_to_candidates(df, MAPPINGS[name])
    monkeypatch.setattr(AU, "_llm_cache_get", lambda key: cand)
    fname = EXAMPLES[name][0]
    stored = df.to_json(date_format="iso", orient="split")
    pdata = P.simple_stage_data({"source": "example", "seq": 1, "method": "YOY"}, None, None,
                                stored, None, "example", fname, None)[0]
    pf = P.simple_stage_filter(pdata)[0]
    stash = P.simple_stage_calc(pf, 60, 1, 1, 0.0046, "mono-c-Si", 14, 12)[0]
    return stash["method"], stash["export"]["rate"]


@pytest.mark.parametrize("name", list(MAPPINGS))
def test_simple_mode_matches_app(name, monkeypatch):
    res = pvcopilot.analyze(name, MAPPINGS[name])
    if any("using your column" in n for n in res.notes):
        # the app itself would pick another column here; compare like with like
        res = pvcopilot.analyze(name, {r: c for r, c in res.mapping.items()
                                       if r != "Time"} | _auto_choice(name))
    method, app_rate = _app_rate(name, monkeypatch)
    (got_method, got), = res.rates.items()
    assert got_method == method
    assert got == pytest.approx(app_rate, abs=1e-6)


def test_advanced_multi_method():
    res = pvcopilot.analyze("pvdaq4", MAPPINGS["pvdaq4"], mode="advanced",
                            methods=["YOY", "LR", "CSD"])
    assert set(res.rates) == {"YOY", "LR", "CSD"}
    assert all(r is not None and -5 < r < 2 for r in res.rates.values())
    assert len(res.figures()) >= 4
    code = res.to_script()
    assert "def run_filters" in code and "compute_csd" in code


def test_no_llm_uses_keyword_matching(monkeypatch, tmp_path):
    for v in ("PVCOPILOT_API_KEY", "OPENAI_API_KEY", "PVCOPILOT_BASE_URL", "OPENAI_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.chdir(tmp_path)          # no .env from the working folder
    from pvcopilot import config
    config.reset()
    res = pvcopilot.analyze("pfaffstaetten")
    assert res.mapping["DC Power"] == "Pdc" and res.mapping["Irradiance"] == "G_POA"
    assert any("matched by name" in n for n in res.notes)
    ref = pvcopilot.analyze("pfaffstaetten", MAPPINGS["pfaffstaetten"])
    assert res.rate == pytest.approx(ref.rate)
