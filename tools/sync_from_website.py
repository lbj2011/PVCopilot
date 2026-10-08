"""Re-sync the package from the pvtools website sources.

When pages/pvcopilot.py or page_supporting_files/*.py change on the website,
run from this folder:

    python tools/sync_from_website.py /path/to/pvtools

It copies the website files into src/pvcopilot and applies the packaging
edits below (imports, user-supplied LLM client, file paths, offline fallbacks).
Every edit asserts it matched exactly, so a website change that breaks one
fails loudly instead of silently. Then run:  pytest tests -q
"""
import shutil, sys
from pathlib import Path

SITE = Path(sys.argv[1]).resolve()
S = Path(__file__).resolve().parents[1] / "src" / "pvcopilot"
CORE = ["analysis_utils.py", "analysis_utils_pkg.py", "code_export.py", "export_lib.py",
        "pvcopilot_filter_functions.py", "diagnostic_prompts.py",
        "pvcopilot_functions_code.txt", "pvcopilot_main_code.txt",
        "pvcopilot_packages_code.txt", "pvcopilot_functions_code_pkg.txt"]
for f in CORE:
    shutil.copy2(SITE / "page_supporting_files" / f, S / "core" / f)
shutil.copy2(SITE / "pages" / "pvcopilot.py", S / "app" / "page.py")
shutil.copy2(SITE / "pages" / "pvcopilot_chat_context.md", S / "app" / "chat_context.md")
for f in ["pvcopilot_dmc_funcs.js", "pvpro_elapsed_ticker.js"]:
    shutil.copy2(SITE / "assets" / f, S / "app" / "assets" / f)
css = (SITE / "assets" / "pvcopilot_styles.css").read_text(encoding="utf-8")
imp = ("@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900"
       "&family=JetBrains+Mono:wght@400;500&display=swap');")
assert imp in css, "font @import changed in pvcopilot_styles.css"
(S / "app" / "assets" / "pvcopilot_styles.css").write_text(
    css.replace(imp, "/* Fonts are bundled locally: see 00_fonts.css (offline package). */"),
    encoding="utf-8")
import re

# ======================= pass 1 =======================



def sub(path, old, new, count=1, regex=False):
    p = S / path
    s = p.read_text(encoding="utf-8")
    n = len(re.findall(old, s)) if regex else s.count(old)
    if count is not None and n != count:
        raise SystemExit(f"{path}: expected {count} of {old!r}, found {n}")
    s = re.sub(old, new, s) if regex else s.replace(old, new)
    p.write_text(s, encoding="utf-8")


# ---------- generic import rewrites -----------------------------------------
for f in ["core/analysis_utils.py", "core/analysis_utils_pkg.py", "core/code_export.py",
          "core/export_lib.py", "core/pvcopilot_filter_functions.py",
          "core/diagnostic_prompts.py", "app/page.py"]:
    sub(f, r"from page_supporting_files\.(\w+) import", r"from pvcopilot.core.\1 import",
        count=None, regex=True)
    sub(f, r"from page_supporting_files import", "from pvcopilot.core import",
        count=None, regex=True)
    sub(f, r"import page_supporting_files\.(\w+) as", r"import pvcopilot.core.\1 as",
        count=None, regex=True)

# ---------- analysis_utils: LLM client + file paths --------------------------
A = "core/analysis_utils.py"
sub(A, "from dotenv import load_dotenv\n", "")
sub(A, "load_dotenv(override=True)\n", "")
sub(A, 'cborg_API_KEY = os.getenv("cborg_api_key")\nOPENAI_API_KEY = os.getenv("OPENAI_API_KEY")\n', "")
sub(A, "client = openai.OpenAI(\n    api_key= OPENAI_API_KEY\n)\n",
    "# Offline package: the user supplies the key/endpoint (pvcopilot.config).\n"
    "from pvcopilot.llm import client, get_model\n")
sub(A, 'LLM_MODEL = "gpt-5.4-mini"\n',
    'LLM_MODEL = "gpt-5.4-mini"   # default only; calls use get_model() (configurable)\n')
sub(A, "model=LLM_MODEL,", "model=get_model(),", count=2)
sub(A, '_LLM_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),\n'
       '                               ".llm_id_cache.json")',
    'from pvcopilot._paths import user_cache_dir as _user_cache_dir\n'
    '_LLM_CACHE_PATH = os.path.join(_user_cache_dir(), "llm_id_cache.json")')
for name in ["pvcopilot_functions_code", "pvcopilot_packages_code", "pvcopilot_main_code"]:
    sub(A, f'open("page_supporting_files/{name}.txt"',
        f'open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "{name}.txt")')

# ---------- code_export ------------------------------------------------------
C = "core/code_export.py"
sub(C, '_INTERNAL_MODULE_PREFIXES = ("page_supporting_files", "pages", "app", "utils", "index")',
    '_INTERNAL_MODULE_PREFIXES = ("pvcopilot",)')
sub(C, "    from pvcopilot.core.analysis_utils import client, LLM_MODEL\n",
    "    from pvcopilot.llm import client, get_model\n")
sub(C, "model=LLM_MODEL,", "model=get_model(),", count=2)

# ---------- the Dash page ----------------------------------------------------
P = "app/page.py"
sub(P, "from app import app\n", "from pvcopilot.app._dash import app\nfrom pvcopilot import _paths\n")
sub(P, "        client as _llm_client,\n        LLM_MODEL as _diagnostic_model,\n",
    "        client as _llm_client,\n")
sub(P, "    from pvcopilot.core.analysis_utils import (\n        client as _llm_client,\n    )",
    "    from pvcopilot.llm import client as _llm_client, get_model as _get_model\n"
    "    _diagnostic_model = None", count=1)
sub(P, "_llm_client is None", "not _llm_client", count=None)
sub(P, "_llm_client is not None", "bool(_llm_client)", count=None)
sub(P, 'model=_diagnostic_model or "gpt-5.4-mini",', 'model=_get_model(),')
sub(P, 'model="gpt-5.4-nano",', 'model=_get_model("fast"),', count=2)
sub(P, 'pd.read_parquet(f"data/{example_filename}")',
    'pd.read_parquet(_paths.example_path(example_filename))')
sub(P, '_CITIES_CSV_PATH = os.path.join("data", "cities15000.csv")',
    '_CITIES_CSV_PATH = str(_paths.data_path("cities15000.csv"))')
sub(P, 'os.path.join(os.path.dirname(__file__), "pvcopilot_chat_context.md")',
    'os.path.join(os.path.dirname(__file__), "chat_context.md")')
print("rewrites OK")

# ======================= pass 2 =======================


A = "core/analysis_utils.py"
# parse_contents(candidates=...) : a user-supplied mapping replaces the LLM call,
# everything after it (quality checks, AC fallback, time index) is unchanged.
sub(A, "def parse_contents(contents=None, filename=None, df=None, progress=None):",
       "def parse_contents(contents=None, filename=None, df=None, progress=None, candidates=None):")
sub(A, "        raw_candidates = _llm_cache_get(cache_key)\n",
       "        raw_candidates = (dict(candidates) if candidates is not None\n"
       "                          else _llm_cache_get(cache_key))\n")
print("rewrite2 OK")

# ======================= pass 3 =======================
p = S / "app/page.py"; s = p.read_text(encoding="utf-8")
old = ('                    "Online usage doesn\'t require "\n'
       '                    "a user API key. If you encounter issues, please ",\n')
new = ('                    ("Local version: this copy runs on your computer. Without AI, or "\n'
       '                     "with a model on this computer, nothing leaves it. With a remote "\n'
       '                     "AI service, column names and data summaries are sent to it (see "\n'
       '                     "AI settings, top right). If you encounter issues, please "),\n')
assert s.count(old) == 1, "note text not found"
s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("rewrite3 OK")

# ======================= pass 4 =======================
p = S / "core/analysis_utils.py"; s = p.read_text(encoding="utf-8")
old = "        _cache_miss = raw_candidates is None\n\n        if _cache_miss:\n"
new = ("        _cache_miss = raw_candidates is None\n\n"
       "        # Offline package: no LLM configured -> keyword matching (same structure).\n"
       "        if _cache_miss and not client:\n"
       "            from pvcopilot.core.heuristics import heuristic_candidates\n"
       "            raw_candidates = heuristic_candidates(df.columns)\n"
       "            _cache_miss = False\n"
       "            mapping_notes.append(\"AI is off (or no API key), so columns were matched by name. \"\n"
       "                                 \"Check the mapping (Advanced mode lets you change it).\")\n\n"
       "        if _cache_miss:\n")
assert s.count(old) == 1
p.write_text(s.replace(old, new), encoding="utf-8")
print("rewrite4 OK")

# ======================= pass 5 =======================
# A failing LLM call (wrong key, no network, unknown model) must not stop the
# analysis: fall back to name matching, say why in the data notes and the terminal.
p = S / "core/analysis_utils.py"; s = p.read_text(encoding="utf-8")
start = "        if _cache_miss:\n            _p(\"Asking AI to identify your columns…\")\n"
end = "            # NOTE: deliberately NOT saved here -- see commit_llm_cache().\n"
assert s.count(start) == 1 and s.count(end) == 1
i = s.index(start); j = s.index(end) + len(end)
body = s[i + len("        if _cache_miss:\n"):j]
body = "".join("    " + l if l.strip() else l for l in body.splitlines(True))
block = ("        if _cache_miss:\n"
         "            try:\n" + body +
         "            except Exception as _llm_err:\n"
         "                from pvcopilot.llm import describe_error as _llm_why, redact as _llm_redact\n"
         "                from pvcopilot.core.heuristics import heuristic_candidates\n"
         "                print(f\"[pvcopilot] AI column identification failed: \"\n"
         "                      f\"{type(_llm_err).__name__}: {_llm_redact(_llm_err)[:300]}\", flush=True)\n"
         "                raw_candidates = heuristic_candidates(df.columns)\n"
         "                _cache_miss = False\n"
         "                mapping_notes.append(\"AI column identification failed (\" + _llm_why(_llm_err)\n"
         "                                     + \"), so columns were matched by name. Check the \"\n"
         "                                     \"mapping, or fix the key in AI settings.\")\n")
s = s[:i] + block + s[j:]
p.write_text(s, encoding="utf-8")
print("rewrite5 OK")
