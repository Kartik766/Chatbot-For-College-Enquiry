"""Hybrid retriever: FAISS semantic search + BM25 keyword search, fused with RRF.

OCR text is noisy and full of names/numbers (packages, companies, fees), so exact
keyword matching complements the embeddings. Both run locally.
"""
import json
import math
import re
from collections import Counter

from . import config

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("a an the of and or to in on for is are was were be by with at as from "
            "what which who how when where do does can i me my you your it its this that "
            "tell about please".split())


def tokenize(text):
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = [len(d) for d in docs]
        self.avg = sum(self.len) / max(1, len(docs))
        df = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - v + 0.5) / (v + 0.5)) for t, v in df.items()}

    def scores(self, query_tokens):
        out = [0.0] * len(self.tf)
        for t in set(query_tokens):
            idf = self.idf.get(t)
            if not idf:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t)
                if f:
                    out[i] += idf * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return out


class Retriever:
    def __init__(self):
        import faiss
        from sentence_transformers import SentenceTransformer

        idx_file = config.INDEX_DIR / "index.faiss"
        if not idx_file.exists() or not config.CHUNKS_JSON.exists():
            raise FileNotFoundError(
                "Index not found. Run: python scripts/ocr.py && python scripts/build_index.py")
        self.chunks = json.load(open(config.CHUNKS_JSON, encoding="utf-8"))
        meta = json.load(open(config.INDEX_DIR / "meta.json"))
        self.index = faiss.read_index(str(idx_file))
        if self.index.ntotal != len(self.chunks):
            raise RuntimeError("chunks.json and the FAISS index are out of sync - rebuild the index.")
        self.model_name = meta["model"]  # must match the model used to build the index
        self.model = SentenceTransformer(self.model_name)
        self.bm25 = BM25([tokenize(f"{c['title']} {c['text']}") for c in self.chunks])

    def _dense(self, query, n):
        q = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True).astype("float32")
        scores, ids = self.index.search(q, n)
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i >= 0]

    def _sparse(self, query, n):
        sc = self.bm25.scores(tokenize(query))
        top = sorted(range(len(sc)), key=lambda i: -sc[i])[:n]
        return [(i, sc[i]) for i in top if sc[i] > 0]

    def search(self, query, k=None, pool=20):
        k = k or config.TOP_K
        dense, sparse = self._dense(query, pool), self._sparse(query, pool)
        fused = Counter()
        for rank, (i, _) in enumerate(dense):
            fused[i] += 1.0 / (60 + rank)
        for rank, (i, _) in enumerate(sparse):
            fused[i] += 1.0 / (60 + rank)
        sim = dict(dense)
        results = []
        for i, score in fused.most_common(k):
            c = dict(self.chunks[i])
            c["score"] = round(score, 5)
            c["similarity"] = round(sim.get(i, 0.0), 3)
            results.append(c)
        return results
