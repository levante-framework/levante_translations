"""
Evaluate translation quality by semantic similarity
===================================================

Method (mirrors “How the evaluation was done”):

1.  Load the master translation table (`summary.csv`).
2.  For every language column (de, es-CO, fr-CA, nl):
    • Drop rows whose translation cell is empty / NaN.  
    • Embed the English sentence and its translation with the LaBSE
      multilingual sentence-transformer.  
    • Compute cosine similarity for each pair
      (≈ 1 → identical meaning, 0 → unrelated).  
3.  Aggregate per language:
      – N (pairs evaluated)  
      – mean similarity  
      – share of pairs < 0.30 (poor)  
      – share of pairs < 0.75 (needs review)  
      – share ≥ 0.75 (good)
"""

# 0.  pip-install once (comment out if already present)
# ----------------------------------------------------
# !pip install -q sentence-transformers

from pathlib import Path
import pandas as pd
import numpy as np
from tqdm.auto import tqdm
from sentence_transformers import SentenceTransformer, util

# 1.  Data ------------------------------------------------------------------
df = pd.read_csv("summary.csv")           # table with english + language cols
lang_cols = ["de", "es-CO", "fr-CA", "nl"]

# 2.  Model -----------------------------------------------------------------
model = SentenceTransformer("sentence-transformers/LaBSE")

results = []

for lang in lang_cols:
    sub = df[["english", lang]].dropna()
    sub = sub[sub[lang].str.strip() != ""]
    if sub.empty:
        continue

    # Embeddings (batch for speed)
    eng_emb   = model.encode(sub["english"].tolist(),
                             convert_to_tensor=True, show_progress_bar=False)
    lang_emb  = model.encode(sub[lang].tolist(),
                             convert_to_tensor=True, show_progress_bar=False)

    sims = util.cos_sim(eng_emb, lang_emb).diagonal().cpu().numpy()

    results.append({
        "language"      : lang,
        "items"         : len(sims),
        "mean_score"    : sims.mean(),
        "<0.30 (count)" : int((sims < 0.30).sum()),
        "<0.75 (count)" : int(((sims >= .30) & (sims < .75)).sum()),
        ">=0.75 (count)": int((sims >= 0.75).sum()),
    })

# 3.  % columns & pretty table ----------------------------------------------
for r in results:
    n = r["items"]
    r["<0.30 (%)"]  = f"{r['<0.30 (count)']/n*100:.1f}%"
    r["<0.75 (%)"]  = f"{r['<0.75 (count)']/n*100:.1f}%"
    r[">=0.75 (%)"] = f"{r['>=0.75 (count)']/n*100:.1f}%"

out = pd.DataFrame(results).set_index("language")
print(out.round(2))
