"""
Project Olist review comments to 2-D and open them in Apple's Embedding Atlas.

Embedding Atlas reuses the Mosaic + DuckDB architecture from dashboard.py and adds a
WebGPU point renderer, density contours, automatic cluster labels and nearest-neighbour
search — so the scatterplot of every review cross-filters with histograms of score,
state, category and lateness. The embedding view needs a WebGPU browser (recent
Chrome/Edge); the side charts and table work everywhere.

    python reviews_atlas.py                 # build web/reviews_xy.parquet, then launch the UI
    python reviews_atlas.py --no-launch     # just build the file

Embedding here is TF-IDF (character n-grams, works for the English synthetic comments and
the Portuguese real ones alike, no model download)
→ 64-d SVD → UMAP. For neural embeddings, skip this script and let the tool do it:
    embedding-atlas web/reviews.parquet --text review_text \
        --model paraphrase-multilingual-MiniLM-L12-v2
"""
import argparse
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import umap
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

WEB = Path(__file__).parent / "web"


def build(src: Path, dst: Path, sample: int, seed: int) -> Path:
    df = pd.read_parquet(src)
    if sample and len(df) > sample:
        df = df.sample(sample, random_state=seed)
    df = df.reset_index(drop=True)

    # Short reviews repeat a lot ("Very good", "Highly recommend"): embed each distinct text once.
    texts = df["review_text"].str.strip()
    uniq, first_row, inv = np.unique(texts.to_numpy(), return_index=True, return_inverse=True)

    tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True)
    X = TruncatedSVD(64, random_state=seed).fit_transform(tfidf.fit_transform(uniq))
    X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-9          # cosine geometry

    xy = umap.UMAP(n_neighbors=15, min_dist=0.1, metric="cosine", random_state=seed).fit_transform(X)
    jitter = np.random.default_rng(seed).normal(0, 0.03 * xy.std(), (len(df), 2))  # spread exact repeats
    df["x"] = (xy[inv, 0] + jitter[:, 0]).astype("float32")
    df["y"] = (xy[inv, 1] + jitter[:, 1]).astype("float32")

    # neighbours = the 10 most similar *distinct* texts, pointing at a row that holds each
    dist, idx = NearestNeighbors(n_neighbors=11, metric="cosine").fit(X).kneighbors(X)
    nbrs = [{"ids": first_row[i[1:]].tolist(), "distances": d[1:].round(4).tolist()}
            for i, d in zip(idx, dist)]
    df["neighbors"] = [nbrs[k] for k in inv]
    df["late"] = np.where(df["late"], "late", "on time")
    df.to_parquet(dst, index=False)
    print(f"wrote {dst} ({len(df):,} reviews)")
    return dst


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=WEB / "reviews.parquet")
    ap.add_argument("--out", type=Path, default=WEB / "reviews_xy.parquet")
    ap.add_argument("--sample", type=int, default=30_000, help="0 = all rows")
    ap.add_argument("--seed", type=int, default=578)
    ap.add_argument("--no-launch", action="store_true")
    a = ap.parse_args()
    out = build(a.src, a.out, a.sample, a.seed)
    if not a.no_launch:
        subprocess.run(["embedding-atlas", str(out), "--text", "review_text",
                        "--x", "x", "--y", "y", "--neighbors", "neighbors"], check=True)
