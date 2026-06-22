#!/usr/bin/env python3
"""
Builds a Chroma vector index from the parsed article JSON files.

Two embedding backends:
  --backend tfidf   : local TF-IDF vectors, no network/model needed.
                       Good for testing the pipeline end-to-end here.
  --backend ollama  : calls a local Ollama embedding model
                       (http://localhost:11434/api/embeddings), this is
                       the production path meant to run on Umar's own
                       machine where Ollama is already installed.

Usage:
    python3 build_index.py articles_2011.json articles_2012.json ... \
        --backend tfidf --persist ./chroma_db
"""
import json
import argparse
import os
import sys

import chromadb


def load_articles(paths):
    all_articles = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            all_articles.extend(json.load(f))
    return all_articles


def make_doc_id(article, idx):
    date = (article.get("date") or "unknown-date").replace(" ", "_").replace(",", "")
    return f"{date}_{idx}"


def embed_text(article):
    """Text actually used for embedding: headline + body, this is what
    gets converted into a vector for semantic search."""
    headline = article.get("headline") or ""
    body = article.get("body") or ""
    return f"{headline}\n\n{body}"


def tfidf_embed_all(texts):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD

    vectorizer = TfidfVectorizer(max_features=20000, stop_words="english")
    tfidf = vectorizer.fit_transform(texts)
    # reduce to a dense fixed-size vector (Chroma wants list[float] per doc)
    n_components = min(256, tfidf.shape[0] - 1, tfidf.shape[1] - 1)
    n_components = max(n_components, 2)
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    reduced = svd.fit_transform(tfidf)
    return reduced.tolist(), vectorizer, svd


def ollama_embed_all(texts, model="nomic-embed-text", host="http://localhost:11434"):
    import urllib.request
    import time

    vectors = []
    failed_indices = []
    total = len(texts)
    for i, t in enumerate(texts):
        payload = json.dumps({"model": model, "prompt": t[:8000]}).encode("utf-8")
        req = urllib.request.Request(
            f"{host}/api/embeddings", data=payload,
            headers={"Content-Type": "application/json"},
        )
        vec = None
        last_err = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
                vec = data["embedding"]
                break
            except Exception as e:
                last_err = e
                time.sleep(2)
        if vec is None:
            print(f"  [{i+1}/{total}] FAILED after 3 attempts: {last_err}")
            vectors.append(None)
            failed_indices.append(i)
        else:
            vectors.append(vec)

        if (i + 1) % 25 == 0 or (i + 1) == total:
            print(f"  [{i+1}/{total}] embedded ({len(failed_indices)} failed so far)")

    if failed_indices:
        print(f"Done embedding. {len(failed_indices)} article(s) failed and will be skipped: {failed_indices}")
    return vectors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="article JSON files to index")
    ap.add_argument("--backend", choices=["tfidf", "ollama"], default="tfidf")
    ap.add_argument("--ollama-model", default="nomic-embed-text")
    ap.add_argument("--persist", default="./chroma_db")
    ap.add_argument("--collection", default="umar_archive")
    args = ap.parse_args()

    articles = load_articles(args.inputs)
    print(f"Loaded {len(articles)} articles from {len(args.inputs)} file(s)")

    texts = [embed_text(a) for a in articles]

    if args.backend == "tfidf":
        print("Embedding backend: TF-IDF (local test mode, no network)")
        vectors, _, _ = tfidf_embed_all(texts)
    else:
        print(f"Embedding backend: Ollama ({args.ollama_model})")
        vectors = ollama_embed_all(texts, model=args.ollama_model)

    client = chromadb.PersistentClient(path=args.persist)
    # fresh collection each run for now
    try:
        client.delete_collection(args.collection)
    except Exception:
        pass
    collection = client.create_collection(args.collection)

    ids, metadatas, documents, kept_vectors = [], [], [], []
    skipped = 0
    for idx, (a, vec) in enumerate(zip(articles, vectors)):
        if vec is None:
            skipped += 1
            continue
        ids.append(make_doc_id(a, idx))
        metadatas.append({
            "date": a.get("date") or "",
            "headline": a.get("headline") or "",
            "byline": a.get("byline") or "",
            "byline_category": a.get("byline_category") or "",
            "source_file": a.get("source_file") or "",
        })
        documents.append(texts[idx])
        kept_vectors.append(vec)
    vectors = kept_vectors
    if skipped:
        print(f"Skipping {skipped} article(s) with failed embeddings.")

    # Chroma batches large adds; keep it simple with one call since our
    # corpus size (~900) is well within a single add.
    collection.add(ids=ids, embeddings=vectors, metadatas=metadatas, documents=documents)

    print(f"Indexed {collection.count()} articles into Chroma at {args.persist} "
          f"(collection: {args.collection})")


if __name__ == "__main__":
    main()
