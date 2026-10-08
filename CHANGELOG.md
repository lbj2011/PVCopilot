# Changelog

## 0.1.0 (unreleased)

First release of the offline package of [PV-Copilot](https://pvtools.lbl.gov/pv-copilot).

- `pvcopilot ui`: the full PV-Copilot web app on your own computer (Simple and
  Advanced modes, PVPRO, AI diagnosis, chat, code export), with an AI on/off
  switch that starts off and a settings panel that reads the API key from a
  `.env` file the user points to.
- `pvcopilot.analyze()`: the same analysis from Python, returning rates,
  intermediate data, figures and a stand-alone reproducible script.
- `pvcopilot analyze`, `examples`, `config`, `shortcut` command-line tools.
- Works without any LLM (column matching by name); any OpenAI-compatible
  endpoint, including local models, when AI is wanted.
- Nine example datasets (PVDAQ and IEA PVPS Task 13 benchmark systems) with
  checked column mappings, and a quick-start notebook.
