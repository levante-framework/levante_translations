## XLIFF Workflow (Parallel to CSV)

This README documents the isolated XLIFF pipeline built from the existing item bank CSV. It does not change or break the current CSV-based production flow.

### Generate XLIFF from CSV

Prereqs:
- Python virtualenv set up (optional): `source .venv/bin/activate 2>/dev/null || true`
- CSV present at `translation_text/item_bank_translations.csv`

Commands:

1) Emit source-only XLIFF (source-language=en) and bilingual XLIFFs aligned to Crowdin

```bash
python3 utilities/csv_to_xliff_converter.py \
  --input translation_text/item_bank_translations.csv \
  --output-dir xliff-production \
  --source-lang en \
  --original item-bank-translations.xlsx \
  --emit-source
```

Outputs in `xliff-production/`:
- `itembank-source-en.xliff` (source-only)
- `itembank-<lang>.xliff` for each target language (de, de-CH, en, en-GH, es-AR, es-CO, fr-CA, nl)

Details:
- Each `trans-unit` has `id` and `resname` set to the source identifier.
- `approved="yes"` is set on all units; target `state` is preserved (translated/new).
- `<file>` attributes are aligned to Crowdin: `source-language`, optional `target-language`, `original="item-bank-translations.xlsx"`.

### Import into a fresh Crowdin project (levante-xliff)

Project settings:
- Source language: English (en)
- Add targets: de, de-CH, en-US (optional), en-GH, es-AR, es-CO, fr-CA, nl (as needed)

Steps:
1) Upload source
   - Crowdin → Files → Upload
   - Select: `xliff-production/itembank-source-en.xliff`
   - This creates `/item-bank-translations.xlsx` as the source file.

2) Upload translations
   - Crowdin → Upload translations → choose `/item-bank-translations.xlsx`
   - Upload the matching file per language:
     - de → `xliff-production/itembank-de.xliff`
     - de-CH → `xliff-production/itembank-de-CH.xliff`
     - en-US (if used as target) → `xliff-production/itembank-en.xliff`
     - en-GH → `xliff-production/itembank-en-GH.xliff`
     - es-AR → `xliff-production/itembank-es-AR.xliff`
     - es-CO → `xliff-production/itembank-es-CO.xliff`
     - fr-CA → `xliff-production/itembank-fr-CA.xliff`
     - nl → `xliff-production/itembank-nl.xliff`
   - Options:
     - Overwrite translations: ON
     - Add as suggestions: OFF
     - Import same as source: OFF

Validation tips:
- If imports show 0, verify `trans-unit id` matches the string identifier in Crowdin and `<file original>` equals `item-bank-translations.xlsx`.
- For legacy projects using en-US as source, regenerate with `--source-lang en-US`.
- To test, modify one target (append " (TEST)") and re-upload with overwrite ON; 1 string should update.

### Notes
- This XLIFF pipeline runs in parallel to the CSV system; no changes to existing deploy scripts are required.
- Generator script: `utilities/csv_to_xliff_converter.py`
- Rebuild command without source-only:

```bash
python3 utilities/csv_to_xliff_converter.py \
  --input translation_text/item_bank_translations.csv \
  --output-dir xliff-production \
  --source-lang en \
  --original item-bank-translations.xlsx
```


