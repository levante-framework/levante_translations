# Write the validation script to a file
code = '''import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import random
import warnings
warnings.filterwarnings("ignore")

CSV_PATH = "translation_text/item_bank_translations.csv"
MODEL_NAME = "sentence-transformers/LaBSE"
LANG_COLS = ["en", "es-CO", "de", "fr-CA", "nl"]
CORRUPT_LANG = {"A_SWAP": "de", "B_BACK": "es-CO", "C_SHUFFLE": "fr-CA"}
OUTPUT_CSV = "embedding_gate_validation.csv"
OUTPUT_PNG = "embedding_gate_validation.png"
THRESHOLD_RANGE = np.arange(0.05, 0.60, 0.005)

print("Loading model...")
model = SentenceTransformer(MODEL_NAME)

print("Loading CSV...")
df = pd.read_csv(CSV_PATH)
df = df.dropna(subset=LANG_COLS).reset_index(drop=True)
print(f"Rows after dropping missing translations: {len(df)}")

print("Encoding all translations...")
embeddings = {}
for lang in LANG_COLS:
    texts = df[lang].tolist()
    embeddings[lang] = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)

emb_matrix = np.stack([embeddings[l] for l in LANG_COLS], axis=1)  # (N, 5, D)

def centroid_distances(emb_mat):
    centroid = emb_mat.mean(axis=1, keepdims=True)  # (N, 1, D)
    dists = 1 - (emb_mat * centroid).sum(axis=2)    # cosine distance (N, 5)
    return dists

baseline_dists = centroid_distances(emb_matrix)  # (N, 5)
lang_to_idx = {l: i for i, l in enumerate(LANG_COLS)}

results = []
all_baseline = baseline_dists.flatten()

def run_corruption(corruption_type, corrupt_lang, corrupt_fn):
    print(f"Running corruption: {corruption_type}...")
    corrupt_idx = lang_to_idx[corrupt_lang]
    hits, misses = 0, 0
    corrupt_dists_list = []

    for i in range(len(df)):
        corrupted = emb_matrix[i].copy()  # (5, D)
        corrupted[corrupt_idx] = corrupt_fn(i, corrupt_lang)
        centroid = corrupted.mean(axis=0, keepdims=True)
        dists = 1 - (corrupted * centroid).sum(axis=1)
        outlier_idx = np.argmax(dists)
        corrupt_dists_list.append(dists[corrupt_idx])
        hit = int(outlier_idx == corrupt_idx)
        hits += hit
        misses += (1 - hit)
        results.append({
            "identifier": df["identifier"].iloc[i],
            "corruption": corruption_type,
            "corrupt_lang": corrupt_lang,
            "corrupt_dist": dists[corrupt_idx],
            "baseline_dist": baseline_dists[i, corrupt_idx],
            "outlier_detected": hit,
        })
    return np.array(corrupt_dists_list)

def swap_fn(i, lang):
    j = random.choice([x for x in range(len(df)) if x != i])
    return embeddings[lang][j]

def back_fn(i, lang):
    return embeddings["en"][i]

def shuffle_fn(i, lang):
    text = df[lang].iloc[i]
    words = text.split()
    if len(words) > 1:
        random.shuffle(words)
    shuffled = " ".join(words)
    return model.encode([shuffled], normalize_embeddings=True)[0]

corrupt_dists = {}
corrupt_dists["A_SWAP"]    = run_corruption("A_SWAP",    CORRUPT_LANG["A_SWAP"],    swap_fn)
corrupt_dists["B_BACK"]    = run_corruption("B_BACK",    CORRUPT_LANG["B_BACK"],    back_fn)
corrupt_dists["C_SHUFFLE"] = run_corruption("C_SHUFFLE", CORRUPT_LANG["C_SHUFFLE"], shuffle_fn)

results_df = pd.DataFrame(results)
results_df.to_csv(OUTPUT_CSV, index=False)

# Find optimal threshold per corruption type
print("\\nOptimal thresholds by F1:")
summary_rows = []
for ctype in ["A_SWAP", "B_BACK", "C_SHUFFLE"]:
    sub = results_df[results_df["corruption"] == ctype]
    best_f1, best_thresh, best_prec, best_rec = 0, 0, 0, 0
    for t in THRESHOLD_RANGE:
        predicted = (sub["corrupt_dist"] > t).astype(int)
        tp = ((predicted == 1) & (sub["outlier_detected"] == 1)).sum()
        fp = ((predicted == 1) & (sub["outlier_detected"] == 0)).sum()
        fn = ((predicted == 0) & (sub["outlier_detected"] == 1)).sum()
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        if f1 > best_f1:
            best_f1, best_thresh, best_prec, best_rec = f1, t, prec, rec
    hits = sub["outlier_detected"].sum()
    n = len(sub)
    summary_rows.append({
        "corruption_type": ctype,
        "n_tested": n,
        "hits": hits,
        "misses": n - hits,
        "best_threshold": round(best_thresh, 3),
        "precision": round(best_prec, 3),
        "recall": round(best_rec, 3),
        "F1": round(best_f1, 3),
    })
    print(f"  {ctype}: threshold={best_thresh:.3f}  P={best_prec:.3f}  R={best_rec:.3f}  F1={best_f1:.3f}")

summary_df = pd.DataFrame(summary_rows)
print("\\nSummary table:")
print(summary_df.to_string(index=False))

# Recommended threshold = mean of best thresholds
recommended_threshold = round(float(np.mean([r["best_threshold"] for r in summary_rows])), 3)
print(f"\\nRecommended gate threshold: {recommended_threshold}")

# Plot
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.suptitle("Embedding Gate Validation: Baseline vs. Corrupted Cosine Distances", fontsize=13)

colors = {"A_SWAP": "#e05c5c", "B_BACK": "#e09c3a", "C_SHUFFLE": "#5c8de0"}
labels = {
    "A_SWAP":    "A: SWAP (wrong-meaning de)",
    "B_BACK":    "B: BACK (English as es-CO)",
    "C_SHUFFLE": "C: SHUFFLE (shuffled fr-CA)",
}
corrupt_lang_map = {"A_SWAP": "de", "B_BACK": "es-CO", "C_SHUFFLE": "fr-CA"}

for ax, ctype in zip(axes, ["A_SWAP", "B_BACK", "C_SHUFFLE"]):
    clang = corrupt_lang_map[ctype]
    cidx  = lang_to_idx[clang]
    base  = baseline_dists[:, cidx]
    corr  = corrupt_dists[ctype]
    best_t = summary_rows[["A_SWAP","B_BACK","C_SHUFFLE"].index(ctype)]["best_threshold"]

    bins = np.linspace(0, max(base.max(), corr.max()) * 1.05, 50)
    ax.hist(base, bins=bins, alpha=0.55, color="#888", label="Baseline", density=True)
    ax.hist(corr, bins=bins, alpha=0.65, color=colors[ctype], label="Corrupted", density=True)
    ax.axvline(best_t, color="black", linestyle="--", linewidth=1.5, label=f"Threshold={best_t:.3f}")
    ax.set_title(labels[ctype], fontsize=10)
    ax.set_xlabel("Cosine distance from centroid")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    f1 = summary_rows[["A_SWAP","B_BACK","C_SHUFFLE"].index(ctype)]["F1"]
    ax.text(0.97, 0.97, f"F1={f1:.3f}", transform=ax.transAxes,
            ha="right", va="top", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

plt.tight_layout()
plt.savefig(OUTPUT_PNG, dpi=150, bbox_inches="tight")
print(f"\\nPlot saved to {OUTPUT_PNG}")
print(f"Full results saved to {OUTPUT_CSV}")
print(f"\\nDone. Use threshold={recommended_threshold} in the main evaluator.")
'''

with open("validate_embedding_gate.py", "w") as f:
    f.write(code)

print("Script written.")
print(f"Lines: {len(code.splitlines())}")