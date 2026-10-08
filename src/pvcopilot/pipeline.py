"""Headless PV-Copilot: data in, degradation rate(s) out — no browser.

>>> import pvcopilot
>>> res = pvcopilot.analyze("pvdaq4")                    # bundled example
>>> res = pvcopilot.analyze("my_system.csv", methods=["YOY", "LR", "CSD"],
...                         mode="advanced")
>>> res.rates              # {'YOY': -0.52, 'LR': -0.61, 'CSD': -0.58}   (%/yr)
>>> res.show()             # the result figures (Plotly)
>>> res.to_script("analysis.py")   # stand-alone script that reproduces the run

How it stays identical to the web app
-------------------------------------
The pipeline is not a re-implementation. It builds the same "exported analysis
script" the app produces in Step 4 (``core.code_export.build_draft_script``),
which is assembled from ``core.export_lib`` and is regression-tested to
reproduce the app's rates on every example dataset, and runs that script's
``prepare -> run_filters -> run_degradation`` on your data in-process.
Column identification is the app's own ``parse_contents`` (LLM + data-quality
checks); pass ``mapping=`` to skip the LLM.
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

METHODS = ("YOY", "LR", "CSD", "HW", "ARIMA", "PVPRO")
ALL_FILTERS = ("timezone", "clearsky", "low-irra-power", "outlier")
ROLES = ("Time", "DC Power", "DC Voltage", "DC Current", "Irradiance", "Module temperature")

DOWNSIZE_AUTO_TARGET = 30000          # same as the app
ADVANCED_FILTER_DEFAULTS = dict(gamma=-0.004, irr_thresh=300, power_ratio=0.02,
                                iqr=1.5, norm_lower=0.01, norm_upper_pct=99)
PVPRO_DEFAULTS = dict(cells_in_series=60, modules_per_string=1, parallel_strings=1,
                      alpha_isc=0.0046, technology="mono-c-Si",
                      days_per_run=14, iterations_per_year=12)


# ---------------------------------------------------------------------------
# result object
# ---------------------------------------------------------------------------
@dataclass
class Result:
    rates: dict                     # {method: %/yr or None}
    mapping: dict                   # role -> column used
    settings: dict                  # everything needed to replay the run (code-export cfg)
    details: dict = field(repr=False, default_factory=dict)
    daily: Any = field(repr=False, default=None)        # daily performance index
    df_all: Any = field(repr=False, default=None)       # every reading, with "norm"
    df_good: Any = field(repr=False, default=None)      # readings kept by the filters
    notes: list = field(default_factory=list)
    log: list = field(repr=False, default_factory=list)
    _ns: dict = field(repr=False, default_factory=dict)

    @property
    def rate(self):
        """Headline rate (%/yr): the first method that produced one."""
        for v in self.rates.values():
            if v is not None:
                return v
        return None

    def summary(self) -> str:
        lines = [f"PV-Copilot result ({self.settings.get('mode')} mode, "
                 f"{self.settings.get('data_file')})"]
        for m, r in self.rates.items():
            lines.append(f"  {m:<6} {r:+.3f} %/yr" if r is not None else f"  {m:<6} n/a")
        if self.df_good is not None and self.df_all is not None:
            lines.append(f"  readings kept: {len(self.df_good):,} of {len(self.df_all):,}")
        lines.append("  mapping: " + ", ".join(f"{k} = {v}" for k, v in self.mapping.items()))
        lines += [f"  note: {n}" for n in self.notes]
        return "\n".join(lines)

    __str__ = summary

    def figures(self):
        """Plotly figures: filtering, daily trend per method, YoY histogram, comparison."""
        ns, figs = self._ns, []
        if "plot_filtering" in ns and self.df_all is not None:
            figs.append(ns["plot_filtering"](self.df_all, self.df_good))
        if "PVPRO" in self.rates:
            if self.rates.get("PVPRO") is not None and "plot_pvpro" in ns:
                figs.append(ns["plot_pvpro"](self.details["PVPRO"]))
            return figs
        for m, r in self.rates.items():
            if r is not None and "plot_daily_trend" in ns:
                figs.append(ns["plot_daily_trend"](self.daily, r, m, self.details.get(m)))
        if self.rates.get("YOY") is not None and "plot_yoy_distribution" in ns:
            figs.append(ns["plot_yoy_distribution"](self.details["YOY"], self.rates["YOY"]))
        if len(self.rates) > 1 and "plot_method_comparison" in ns:
            figs.append(ns["plot_method_comparison"](self.rates))
        return figs

    def show(self):
        for f in self.figures():
            f.show()

    def save_figures(self, folder="pvcopilot_figures", fmt="html"):
        """Write every figure to `folder` (html needs nothing extra; png/svg need kaleido)."""
        os.makedirs(folder, exist_ok=True)
        out = []
        for i, f in enumerate(self.figures(), 1):
            p = os.path.join(folder, f"figure_{i}.{fmt}")
            f.write_html(p, include_plotlyjs=True) if fmt == "html" else f.write_image(p)
            out.append(p)
        return out

    def to_script(self, path=None, data_file=None) -> str:
        """The stand-alone Python script for this run (same as the app's Step 4)."""
        from pvcopilot.core import code_export
        cfg = dict(self.settings)
        if data_file:
            cfg["data_file"] = os.path.basename(data_file)
        code = code_export.build_draft_script(cfg)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
        return code

    def to_dict(self):
        return {"rates": self.rates, "mapping": self.mapping, "notes": self.notes,
                "settings": {k: v for k, v in self.settings.items() if k != "expected"},
                "n_readings": None if self.df_all is None else len(self.df_all),
                "n_kept": None if self.df_good is None else len(self.df_good)}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def read_data(data):
    """DataFrame | path (.csv/.xlsx/.parquet) | bundled example name -> (df, file name)."""
    from pvcopilot import examples
    if isinstance(data, pd.DataFrame):
        return data.copy(), "data.csv"
    data = os.fspath(data)
    if not os.path.exists(data):
        try:
            p = examples.example_file(data)
            return pd.read_parquet(p), os.path.basename(p)
        except KeyError:
            raise FileNotFoundError(f"{data!r} is neither a file nor a bundled example "
                                    f"({', '.join(examples.EXAMPLES)})") from None
    name = os.path.basename(data)
    low = name.lower()
    if low.endswith(".parquet"):
        df = pd.read_parquet(data)
    elif low.endswith((".xls", ".xlsx")):
        df = pd.read_excel(data)
    else:
        try:
            df = pd.read_csv(data, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(data, encoding="latin-1")
    return df, name


def _mapping_to_candidates(df, mapping):
    unknown = set(mapping) - set(ROLES)
    if unknown:
        raise ValueError(f"unknown mapping role(s) {sorted(unknown)}; use {ROLES}")
    for role, col in mapping.items():
        if col and col != "__index__" and col not in df.columns:
            raise ValueError(f"mapping[{role!r}] = {col!r} is not a column of the data")
    cand = {r: [mapping[r]] if mapping.get(r) else []
            for r in ("DC Power", "DC Voltage", "DC Current", "Irradiance", "Module temperature")}
    cand.update({"AC Power": [], "AC Voltage": [], "AC Current": []})
    t = mapping.get("Time")
    cand["Time"] = [t] if t and t != "__index__" else []
    return cand


def identify_columns(df, mapping=None, progress=None):
    """The app's column identification. Returns (df with DatetimeIndex, mapping, notes)."""
    from pvcopilot.core.analysis_utils import parse_contents
    cand = None
    if mapping:
        cand = _mapping_to_candidates(df, mapping)
    # no mapping and no LLM -> parse_contents falls back to keyword matching
    out_df, _table, mapped, _code, notes = parse_contents(df=df, progress=progress,
                                                         candidates=cand)
    if out_df is None or not mapped:
        raise RuntimeError("Could not identify the required columns. Pass mapping={...} "
                           f"with the roles {ROLES[1:]} (DC Power and Irradiance are required).")
    notes = list(notes or [])
    if mapping:
        # An explicit mapping is final: parse_contents may prefer another column
        # (e.g. the irradiance channel with the most data); the user's choice wins.
        mapped = dict(mapped)
        for role, col in mapping.items():
            if role == "Time" or not col:
                continue
            auto = mapped.get(role)
            if auto != col:
                if auto:   # notes about the column we are NOT using are moot
                    notes = [n for n in notes if f"'{auto}'" not in n]
                    notes.append(f"{role}: using your column '{col}' "
                                 f"(automatic choice would be '{auto}').")
                mapped[role] = col
    for req in ("DC Power", "Irradiance"):
        if not mapped.get(req):
            raise RuntimeError(f"No {req} column found (mapping so far: {mapped}). "
                               "Pass it explicitly with mapping={...}.")
    return out_df, dict(mapped), notes


def _auto_downsize_factor(n_rows):
    if n_rows <= DOWNSIZE_AUTO_TARGET:
        return None
    return max(int(np.ceil(n_rows / DOWNSIZE_AUTO_TARGET)), 2)


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------
def analyze(data, mapping=None, *, methods=("YOY",), mode="simple",
            filters=None, filter_params=None, clearsky=None, method_params=None,
            pvpro=None, downsize="auto",
            env_file=None, key_var=None, base_url=None, model=None,
            verbose=False) -> Result:
    """Run PV-Copilot's degradation analysis and return a :class:`Result`.

    data         DataFrame, file path (.csv/.xlsx/.parquet) or example name
                 (see ``pvcopilot.list_examples()``)
    mapping      {role: column}; roles Time, DC Power, DC Voltage, DC Current,
                 Irradiance, Module temperature. None -> the LLM identifies them
                 (or, with no LLM configured, keyword matching on the names).
    methods      any of YOY, LR, CSD, HW, ARIMA — or ["PVPRO"] (needs V, I, T)
    mode         "simple"   : the app's Simple mode — fixed filter chain with
                              data-driven thresholds; one method (falls back
                              to LR when the method gives no rate)
                 "advanced" : the app's Advanced mode — choose `filters` and
                              `filter_params`, several methods side by side
    filters      advanced: subset of {"timezone","clearsky","low-irra-power","outlier"}
                 (default: all)
    filter_params advanced: gamma, irr_thresh, power_ratio, iqr, norm_lower,
                 norm_upper_pct (defaults as in the app). simple: overrides of the
                 estimated thresholds.
    clearsky     advanced: csi_threshold, day_fraction, and optional latitude,
                 longitude, tilt, azimuth for a modelled (pvlib) clear-sky reference
    method_params yoy_window, hw_period, arima_p/d/q/s
    pvpro        PVPRO settings: cells_in_series, modules_per_string,
                 parallel_strings, alpha_isc, technology, days_per_run,
                 iterations_per_year
    downsize     "auto" (block-average to <= 30 000 rows, as the app), None, or a factor
    env_file, key_var, base_url, model   where to read the key and which endpoint /
                 model to use (see pvcopilot.configure); the key itself is never passed
    """
    import contextlib
    import io

    from pvcopilot import config
    from pvcopilot.core import code_export
    from pvcopilot.core.estimate import estimate_filter_params

    if env_file or key_var or base_url or model:
        config.configure(env_file=env_file, key_var=key_var, base_url=base_url, model=model)

    methods = [m.upper() for m in ([methods] if isinstance(methods, str) else methods)]
    bad = [m for m in methods if m not in METHODS]
    if bad:
        raise ValueError(f"unknown method(s) {bad}; choose from {METHODS}")
    if "PVPRO" in methods and methods != ["PVPRO"]:
        raise ValueError('PVPRO runs on its own: methods=["PVPRO"]')
    mode = mode.lower()
    if mode not in ("simple", "advanced"):
        raise ValueError('mode must be "simple" or "advanced"')
    if mode == "simple" and len(methods) > 1:
        raise ValueError("simple mode computes one method; use mode='advanced' to compare")

    progress = (lambda m: print("·", m)) if verbose else None
    raw, data_file = read_data(data)
    df, mapped, notes = identify_columns(raw, mapping, progress)
    if methods == ["PVPRO"]:
        missing = [r for r in ("DC Voltage", "DC Current", "Module temperature")
                   if not mapped.get(r)]
        if missing:
            raise RuntimeError(f"PVPRO needs {', '.join(missing)} (mapping: {mapped})")

    # ---- the exported-script pipeline, built with this run's settings -------
    if downsize == "auto":
        factor = _auto_downsize_factor(len(df))
    else:
        factor = float(downsize) if downsize else None

    cfg = {"mode": mode, "data_file": data_file, "mapping": mapped,
           "downsize_factor": factor, "methods": methods,
           "filters": list(filters if filters is not None else ALL_FILTERS),
           "clearsky": dict(clearsky or {}),
           "method_params": dict(method_params or {}),
           "pvpro_kwargs": {**PVPRO_DEFAULTS, **(pvpro or {})} if methods == ["PVPRO"] else {},
           "filter_params": {}, "expected": {}}
    bad = set(cfg["filters"]) - set(ALL_FILTERS)
    if bad:
        raise ValueError(f"unknown filter(s) {sorted(bad)}; choose from {ALL_FILTERS}")

    # Settings and functions first (filter thresholds may depend on prepared data).
    ns = _load_script(code_export.build_draft_script(cfg))
    log = io.StringIO()
    with contextlib.redirect_stdout(log), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        prepared = ns["prepare"](df)

        if mode == "simple":
            est = estimate_filter_params(prepared, mapped) or {}
            fp = {"irr_thresh": est.get("param-irr-thresh", {}).get("value", 300),
                  "power_ratio": est.get("param-power-ratio", {}).get("value", 0.02),
                  "gamma": est.get("param-gamma", {}).get("value", -0.004),
                  "iqr": est.get("param-iqr-multiplier", {}).get("value", 1.5)}
        else:
            fp = dict(ADVANCED_FILTER_DEFAULTS)
        fp.update(filter_params or {})
        cfg["filter_params"] = fp
        ns = _load_script(code_export.build_draft_script(cfg))   # final settings baked in

        df_all, df_good = ns["run_filters"](prepared)
        if len(df_good) == 0:
            raise RuntimeError("Every reading was removed by the filters.")
        rates, details, daily = ns["run_degradation"](df_good)

    rates = {m: (None if r is None or not np.isfinite(r) else float(r)) for m, r in rates.items()}
    try:   # remember the LLM's column mapping for this column set (as the app does)
        from pvcopilot.core.analysis_utils import commit_llm_cache
        commit_llm_cache(df)
    except Exception:
        pass
    cfg["expected"] = {m: r for m, r in rates.items() if r is not None}
    lines = [l for l in log.getvalue().splitlines() if l.strip()]
    notes += [l[len("note: "):] for l in lines if l.startswith("note: ")]
    if verbose:
        for l in lines:
            print("·", l)
    return Result(rates=rates, mapping=mapped, settings=cfg, details=details, daily=daily,
                  df_all=df_all, df_good=df_good, notes=notes, log=lines, _ns=ns)


def _load_script(code):
    ns = {"__name__": "pvcopilot_exported_run"}
    exec(compile(code, "<pvcopilot exported script>", "exec"), ns)
    return ns
