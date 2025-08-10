# XCOMET-XL Evaluation for Levante Translations

This folder provides a ready-to-run workflow to evaluate translation quality using Unbabel's XCOMET-XL via the official COMET toolkit.

XCOMET-XL is a reference-based COMET model that can produce segment-level scores and (via the Python API) error spans/metadata.


## Prerequisites
- Python 3.9+
- Accept the model card terms for `Unbabel/XCOMET-XL` on Hugging Face (required by COMET to download the checkpoint)
- Note: XCOMET-XL checkpoint is licensed CC-BY-NC-SA (non-commercial). COMET toolkit is open source. See Licensing below


## Install
```bash
cd xcomet
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

This installs COMET and helpers. If you intend to run spans via the Python API, this will also pull PyTorch as a dependency.


## Inputs
The runner can consume a Levante CSV containing at least the following columns:
- `item_id`
- `en` (source)
- `<lang_code>` (target; e.g., `es-CO`, `de`, `fr-CA`, `nl`)

References (human-approved translations) are optional and recommended for XCOMET-XL. If you do not have a reference set for the target language, the script can still run an alternative QE model (`Unbabel/COMETKiwi-xl`) by passing `--allow_qe_fallback`. However, for strict XCOMET-XL, provide `--ref_csv` or `--ref_txt`.


## Quick start (XCOMET-XL, CLI path)
Assuming you have reference translations for `es-CO`:
```bash
cd xcomet && source .venv/bin/activate
python run_xcomet.py \
  --lang es-CO \
  --csv ../web-dashboard/public/translation_master.csv \
  --out_dir ./output \
  --use_cli \
  --model Unbabel/XCOMET-XL
```
This will:
- Build `src.txt`, `hyp.txt`, and `ref.txt` under `output/es-CO/`
- Run `comet-score` with XCOMET-XL and write `scores.json`
- Generate `report.md` summarizing system- and segment-level results

If you prefer using the Python API (to export spans/metadata):
```bash
python run_xcomet.py \
  --lang es-CO \
  --csv ../web-dashboard/public/translation_master.csv \
  --out_dir ./output \
  --use_api \
  --spans \
  --model Unbabel/XCOMET-XL
```


## Without references (QE fallback)
If you do not have references, you may run a QE model instead:
```bash
python run_xcomet.py \
  --lang es-CO \
  --csv ../web-dashboard/public/translation_master.csv \
  --out_dir ./output \
  --use_api \
  --allow_qe_fallback
```
This will automatically switch to `Unbabel/wmt22-cometkiwi-da` and produce a report without references. Note: This is not XCOMET-XL and is provided for convenience.


## Report outputs
- `output/<lang>/scores.json`: Raw COMET outputs
- `output/<lang>/report.md`: Aggregated results (mean score, worst segments, distribution)
- If `--spans`, span metadata per segment is also included in `scores_with_spans.json`


## Notes
- Ensure your `unbabel-comet` version (see `requirements.txt`) matches the model’s release notes for compatibility
- If CLI downloads fail, confirm: (1) you accepted the model card; (2) you are authenticated with `huggingface-cli login`


## Licensing
- XCOMET-XL weights: CC-BY-NC-SA; commercial use requires permission from Unbabel
- COMET toolkit: Open source; see the project license
- Generated reports and scores: follow your organization’s data policies
