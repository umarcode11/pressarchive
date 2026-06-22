#!/usr/bin/env python3
"""
Searches the Chroma index of Umar's archive (built by build_index.py) for
articles relevant to a given query or claim.

Usage (standalone, for testing):
    python3 archive_search.py "PTI ban court ruling" --top-k 5

Used as a library (for wiring into an OpenClaw skill):
    from archive_search import search_archive
    results = search_archive("PTI ban court ruling", top_k=5)
"""
import argparse
import json
import sys
import urllib.request

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "umar_archive"
OLLAMA_HOST = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"


def embed_query(text, model=EMBED_MODEL, host=OLLAMA_HOST):
    payload = json.dumps({"model": model, "prompt": text[:8000]}).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/embeddings", data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["embedding"]


def search_archive(query, top_k=5, persist_path=CHROMA_PATH, collection_name=COLLECTION_NAME):
    """Returns a list of dicts: headline, date, byline, source_file, excerpt, distance."""
    import chromadb

    client = chromadb.PersistentClient(path=persist_path)
    collection = client.get_collection(collection_name)

    query_vec = embed_query(query)
    results = collection.query(query_embeddings=[query_vec], n_results=top_k)

    out = []
    ids = results.get("ids", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    documents = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i in range(len(ids)):
        meta = metadatas[i] or {}
        doc = documents[i] or ""
        out.append({
            "id": ids[i],
            "headline": meta.get("headline", ""),
            "date": meta.get("date", ""),
            "byline": meta.get("byline", ""),
            "source_file": meta.get("source_file", ""),
            "excerpt": doc[:400],
            "distance": distances[i],
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="Search Umar's article archive by meaning, not just keywords.")
    ap.add_argument("query", help="The claim, topic, or question to search for")
    ap.add_argument("--top-k", type=int, default=5, help="Number of results to return (default 5)")
    ap.add_argument("--persist", default=CHROMA_PATH, help="Path to the Chroma DB (default ./chroma_db)")
    args = ap.parse_args()

    try:
        results = search_archive(args.query, top_k=args.top_k, persist_path=args.persist)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    if not results:
        print(json.dumps({"results": [], "message": "No matching articles found."}))
        return

    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
