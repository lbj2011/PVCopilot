"""Keyword column matching, used when no LLM is configured.

Produces the same ``candidates`` structure the LLM returns in parse_contents,
so everything downstream (data-quality checks, AC fallback, V*I power, time
index) is unchanged. Less robust than the LLM on unusual names: check the
mapping (Advanced mode, or ``Result.mapping``) and override it if needed.
"""
from __future__ import annotations

import re

# role -> (patterns that must match, patterns that disqualify); best first
_RULES = {
    "Irradiance": ([r"poa", r"irr", r"g_?poa", r"\bgpoa\b", r"pyrano", r"insol", r"solirr",
                    r"radiation", r"\bghi\b", r"\bgti\b", r"w/?m2", r"^g$", r"^g_"],
                   [r"model", r"clear", r"\bcs\b", r"ghi_?cs"]),
    "Module temperature": ([r"mod\w*_?temp", r"temp\w*_?mod", r"t_?mod", r"backofmodule",
                            r"back_?of", r"panel_?temp", r"cell_?temp", r"t_?cell", r"\bbom\b"],
                           [r"amb", r"air"]),
    "DC Power": ([r"dc_?power", r"p_?dc", r"pdc", r"p_?mpp", r"pmpp", r"pmp\b", r"dc.*\bw\b",
                  r"dc_?kw"], [r"\bac\b", r"pac", r"ac_"]),
    "AC Power": ([r"ac_?power", r"p_?ac", r"pac\b", r"^power$", r"power", r"energy", r"kwh"],
                 [r"dc", r"factor", r"reactive", r"apparent", r"var\b", r"pf\b"]),
    "DC Voltage": ([r"dc_?volt", r"v_?dc", r"vdc", r"u_?mpp", r"v_?mpp", r"vmp", r"input_?volt",
                    r"dc.*\bv\b"], [r"\bac\b", r"vac", r"ac_"]),
    "AC Voltage": ([r"ac_?volt", r"v_?ac", r"vac\b"], []),
    "DC Current": ([r"dc_?curr", r"i_?dc", r"idc", r"i_?mpp", r"imp\b", r"input_?curr",
                    r"dc.*\ba\b"], [r"\bac\b", r"iac", r"ac_"]),
    "AC Current": ([r"ac_?curr", r"i_?ac", r"iac\b"], []),
    "Time": ([r"time", r"date", r"timestamp", r"datetime", r"^ts$", r"measured_on"], []),
}


def _norm(name):
    s = str(name).lower()
    s = re.sub(r"[\[\]()°{}]", " ", s)
    s = re.sub(r"[\s\-\.]+", "_", s).strip("_")
    return s


def heuristic_candidates(columns, max_per_role=3):
    cols = list(columns)
    out = {}
    for role, (want, avoid) in _RULES.items():
        scored = []
        for c in cols:
            n = _norm(c)
            if any(re.search(a, n) for a in avoid):
                continue
            hits = [k for k, w in enumerate(want) if re.search(w, n)]
            if hits:
                scored.append((min(hits), len(n), c))
        out[role] = [c for _, _, c in sorted(scored)[:max_per_role]]
    # a column found as DC power must not also be the AC candidate
    out["AC Power"] = [c for c in out["AC Power"] if c not in out["DC Power"]]
    return out
