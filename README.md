# RCPIT Enquiry Chatbot — RAG edition

Flask + FAISS + BM25 + Groq (Llama). Answers questions from the 742-page RCPIT PDF and shows
the **PDF pages / website links** each answer came from. No database server, no Chroma, and
no OCR while chatting.

```
742-page PDF -> smart OCR (resumable) -> clean -> page-aware chunks -> embeddings -> FAISS (on disk)
question -> hybrid search (FAISS semantic + BM25 keyword) -> top 5 chunks -> Groq/Llama -> answer + pages
```

## What is already done for you
Your PDF turned out to be **726 scanned pages and only 16 with a text layer**, so OCR was needed.
It has already been run (200 DPI, Tesseract), so this folder ships with:

| File | Contents |
|---|---|
| `output/ocr_pages.json` | text for all 742 pages (726 OCR, 16 from the PDF text layer) |
| `output/chunks.json` | 188 chunks: 170 from the scanned pages (~350 words, with page range, title, URL) + 18 curated sections from `data/knowledge.pdf` |

Still to do on your PC: **build the embedding index** (needs to download the embedding model once) and add your Groq key.

## The demo website + chat widget
`python app.py` -> open http://localhost:3000 : a dummy RCPIT college website (`static/index.html`). The round chat button at the
bottom-right opens the chatbot panel (`static/widget.js`, styles in `static/site.css`). The old full-page chat is still at `/chat.html`.
Optional: drop a campus photo at `static/site/hero.jpg` for the hero banner.

## Curated knowledge base
`data/knowledge.pdf` (fees, seat matrix, placements, faculty, ...) is indexed next to the scanned pages, one chunk per section.
Sources from it show as "Knowledge Base - ... · curated info", and the prompt prefers it for fees, seats, contacts and headline
placement numbers. Edit/replace that PDF and re-run `python scripts/build_index.py` to update.

## Setup (Windows; macOS/Linux is the same)
1. Python 3.10+.
2. `copy .env.example .env`, then put your `GROQ_API_KEY` in `.env`.
3. Install and build:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python scripts/build_index.py      # embeds chunks -> output/vector_index/ (a few minutes, once)
   python app.py                      # http://localhost:3000
   ```
   `run.bat` / `run.sh` do the venv + install + start for you (run `build_index.py` once before).

Tesseract is only needed if you re-run OCR. On Windows install it and set `TESSERACT_CMD` in `.env`.

## Scripts
| Command | What it does |
|---|---|
| `python scripts/ocr.py` | OCR. **Resumable**: progress is saved per page in `output/ocr_progress.jsonl`; run it again after a crash and it continues. `--restart` starts over, `--workers N` sets parallelism. Pages that already contain selectable text are not OCR'd. |
| `python scripts/build_index.py` | clean -> chunk -> embed -> FAISS. `--chunks-only` skips the embedding step; `--model NAME` picks another sentence-transformers model. |
| `python app.py` | chat server + UI. |

## Groq model
Nothing is hard-coded. Leave `GROQ_MODEL` empty and the app asks Groq which models your key can use and
picks a Llama one (prefers `llama-3.3-70b-versatile`, then `llama-3.1-8b-instant`, else any other Llama).
If a configured model gets removed, it re-resolves automatically. See what is available at
`http://localhost:3000/api/models`.

## Tuning (`.env`)
`TOP_K` (chunks sent to the LLM, default 5), `CHUNK_WORDS` / `CHUNK_OVERLAP`
(changing these means re-running `build_index.py`), `EMBED_MODEL`, `PORT`, `HISTORY_MESSAGES`.

## Layout
```
app.py                Flask API + serves the UI
rag/cleaning.py       strips browser headers/footers/menus, reads title + URL, chunks by page range
rag/retriever.py      FAISS + BM25 fused with reciprocal-rank fusion
rag/llm.py            Groq client with model auto-resolution
scripts/ocr.py        smart resumable OCR
scripts/build_index.py
static/               the original chat UI, now with source chips under answers
output/               ocr_pages.json, chunks.json, vector_index/ (created by build_index.py)
```

## Notes
- The PDF is a browser print-out of rcpit.ac.in, so OCR text can have typos in tables (about half
  the pages are placement-record tables). The prompt tells the model to flag unclear numbers
  instead of guessing; for fees or dates, confirm on the official site.
- The PDF itself is not served by the app; sources link to the original rcpit.ac.in page.
- Answers that are not in the PDF get a "contact the college" reply rather than an invented one.
