"""Clean OCR output -> chunks.json -> embeddings -> FAISS index (all local files).

    python scripts/build_index.py
    python scripts/build_index.py --model BAAI/bge-small-en-v1.5
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rag import config  # noqa: E402
from rag.cleaning import chunk_groups, clean_pages, group_pages, knowledge_chunks  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=config.EMBED_MODEL)
    ap.add_argument("--chunk-words", type=int, default=config.CHUNK_WORDS)
    ap.add_argument("--overlap", type=int, default=config.CHUNK_OVERLAP)
    ap.add_argument("--chunks-only", action="store_true", help="stop after writing chunks.json")
    args = ap.parse_args()

    if not config.OCR_PAGES_JSON.exists():
        sys.exit("output/ocr_pages.json not found. Run: python scripts/ocr.py")

    pages = json.load(open(config.OCR_PAGES_JSON, encoding="utf-8"))
    cleaned = clean_pages(pages)
    groups = group_pages(cleaned)
    chunks = chunk_groups(groups, args.chunk_words, args.overlap, config.MIN_CHUNK_WORDS)
    kb = config.KNOWLEDGE_PDF
    if kb.exists():
        extra = knowledge_chunks(kb, args.chunk_words, args.overlap)
        for c in extra:
            c["id"] = len(chunks)
            chunks.append(c)
        print(f"+ {len(extra)} chunks from curated {kb.name}")
    json.dump(chunks, open(config.CHUNKS_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(pages)} pages -> {len(groups)} documents -> {len(chunks)} chunks "
          f"-> {config.CHUNKS_JSON}")
    if args.chunks_only:
        return

    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer

    print(f"Loading embedding model: {args.model}")
    model = SentenceTransformer(args.model)
    # Title is prepended so "placement", "hostel", ... help matching.
    texts = [f"{c['title']}. {c['text']}" for c in chunks]
    emb = model.encode(texts, batch_size=32, show_progress_bar=True,
                       normalize_embeddings=True, convert_to_numpy=True).astype("float32")

    index = faiss.IndexFlatIP(emb.shape[1])  # cosine (vectors are normalized)
    index.add(emb)
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(config.INDEX_DIR / "index.faiss"))
    json.dump({"model": args.model, "dim": int(emb.shape[1]), "count": len(chunks)},
              open(config.INDEX_DIR / "meta.json", "w"))
    print(f"FAISS index saved ({len(chunks)} vectors, dim {emb.shape[1]}) -> {config.INDEX_DIR}")


if __name__ == "__main__":
    main()
