"""
Translation-quality analysis for Levante COMET scores
====================================================

The script…

1.  Loads the original Excel workbook (`levante_comet_scores.xlsx`).
2.  For every language sheet (`de`, `nl`, `es-CO`, `fr-CA`, …) it
    - counts how many items fall into three quality bands
      -  low   : COMET < 0.30  
      - medium : 0.30 ≤ COMET < 0.75  
      - high   : COMET ≥ 0.75
    - derives the corresponding percentages.
    - records the mean COMET score.
3.  Consolidates everything into a tidy summary `DataFrame`.
4.  Saves the summary to `summary_from_python.csv` and prints it.

You can extend the `LANG_SHEETS` list if more language tabs are added.
"""
import pandas as pd

# ----------------------------------------------------------------------
# 1.  Parameters & helpers
# ----------------------------------------------------------------------
EXCEL_FILE   = "levante_comet_scores.xlsx"
SUMMARY_FILE = "summary_from_python.csv"
LANG_SHEETS  = ["de", "nl", "es-CO", "fr-CA"]          # adjust if needed
BINS         = [0.0, 0.30, 0.75, 1.01]                 # upper edge exclusive
BIN_LABELS   = ["<0.30", "<0.75", ">=0.75"]            # human-readable

# ----------------------------------------------------------------------
# 2.  Iterate through each language worksheet
# ----------------------------------------------------------------------
rows = []

for lang in LANG_SHEETS:
    df = pd.read_excel(EXCEL_FILE, sheet_name=lang)

    # --- basic sanity checks ------------------------------------------
    if {"item_id", "score"}.difference(df.columns):
        raise ValueError(f"Sheet {lang} missing expected columns.")

    # --- histogram of score bins --------------------------------------
    hist = pd.cut(df["score"], BINS, right=False, labels=BIN_LABELS).value_counts() \
              .reindex(BIN_LABELS, fill_value=0)

    # --- summary record -----------------------------------------------
    totals = {
        "language"       : lang,
        "items"          : len(df),
        "mean_score"     : df["score"].mean().round(2)
    }
    # absolute counts
    totals.update({f"{band} (count)": int(hist[band]) for band in BIN_LABELS})
    # percentages
    totals.update({f"{band} (%)"   : f"{(hist[band] / len(df) * 100):.1f}%"
                   for band in BIN_LABELS})

    rows.append(totals)

# ----------------------------------------------------------------------
# 3.  Build & save summary table
# ----------------------------------------------------------------------
summary = pd.DataFrame(rows).set_index("language")
summary.to_csv(SUMMARY_FILE)

# optional screen output
print("Summary of COMET-quality bands\n" + "-"*34)
print(summary)
print(f"\nSaved to: {SUMMARY_FILE}")
