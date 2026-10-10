# Chatbot-For-College-Enquiry
AI-powered enquiry assistant for R. C. Patel Institute of Technology, Shirpur. Answers admissions, fees, programs, hostel and placement questions in English, Hindi and Marathi using Retrieval-Augmented Generation, with source references for every answer.  Topics
# RCPIT College Enquiry Assistant

A multilingual AI assistant that gives prospective students and parents quick, reliable answers about
**R. C. Patel Institute of Technology, Shirpur**. It appears on the website as a chat button in the
bottom-right corner and answers questions about admissions, fees, branches, hostel, placements and more.

## Highlights

- **Grounded answers.** Replies are generated from official college information using Retrieval-Augmented Generation (RAG), not from the model's memory.
- **Source references.** Every answer shows where the information came from.
- **Multilingual.** Understands questions and replies in English, Hindi and Marathi.
- **Instant access.** No sign-up, name or phone number needed before getting an answer.
- **Honest fallback.** If the information is not available, it says so and gives the college contact details.
- **Lightweight.** Runs locally with no separate database server.

## How it works

```
 Website chat widget ──► Flask API ──► Hybrid retrieval ──► Groq (Llama) ──► Answer + sources
 (static/widget.js)      (app.py)      FAISS + BM25
```

1. **Ingestion.** Official college content and a curated knowledge base are extracted (with OCR where needed), cleaned of headers, footers and menus, and split into chunks of about 350 words that remember their page numbers.
2. **Indexing.** Each chunk is embedded with a sentence-transformer model and stored in a local FAISS index.
3. **Retrieval.** Semantic search (FAISS) and keyword search (BM25) are combined to pick the five most relevant chunks. Keyword search helps with names, companies and numbers.
4. **Generation.** A Llama model through the Groq API writes the answer using only those chunks.
5. **Languages.** Hindi and Marathi questions are detected, translated to English for searching, and answered in the user's own language.

## Tech stack

Python · Flask · FAISS · sentence-transformers · BM25 · Groq API (Llama) · Tesseract OCR · PyMuPDF · HTML / CSS / JavaScript

## Getting started

**Requirements:** Python 3.10 or newer, a free [Groq API key](https://console.groq.com/keys), and internet access (the embedding model downloads on first use).

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
copy .env.example .env            # Windows  (cp .env.example .env on macOS / Linux)
# open .env and set GROQ_API_KEY

# 4. Build the search index (once)
python scripts/build_index.py

# 5. Run
python app.py
```

Open **http://localhost:3000** and click the chat button in the bottom-right corner.
The full-page chat is also available at **/chat.html**.

## Configuration

Settings live in `.env`. Only `GROQ_API_KEY` is required.

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | – | Your Groq key |
| `GROQ_MODEL` | *(empty)* | Leave empty to auto-select an available Llama model; or pin one. See `/api/models` |
| `EMBED_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model (rebuild the index after changing) |
| `TOP_K` | `5` | Chunks sent to the language model |
| `CHUNK_WORDS` / `CHUNK_OVERLAP` | `350` / `60` | Chunk size (rebuild the index after changing) |
| `HISTORY_MESSAGES` | `6` | Recent messages remembered per conversation |
| `PORT` | `3000` | Server port |
| `TESSERACT_CMD` | – | Path to Tesseract (Windows, only needed for OCR) |

## Updating the knowledge

| To change… | Do this |
|---|---|
| The curated knowledge base | Edit `data/knowledge.pdf` (section headings in capitals ending with a colon, e.g. `FEE STRUCTURE 2025-26:`), then run `python scripts/build_index.py` |
| The official content | Put the new PDF at `data/Merged_data.pdf`, run `python scripts/ocr.py --restart`, then `python scripts/build_index.py` |

OCR requires [Tesseract](https://github.com/tesseract-ocr/tesseract) to be installed. It saves progress page by
page, so `python scripts/ocr.py` resumes after an interruption. Pages that already contain text are not OCR'd.
Processed text is included in `output/`, so OCR is not needed just to run the project.

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/chat` | POST | Body `{ "sessionId", "message" }` → `{ "reply", "sources" }` |
| `/api/chat/<sessionId>` | DELETE | Clear a conversation |
| `/api/suggestions` | GET | Quick-question chips |
| `/api/health` | GET | Server and index status |
| `/api/models` | GET | Groq models available to your key |

## Project structure

```
app.py                 Flask server and chat API
rag/
  cleaning.py          Text cleaning and chunking
  retriever.py         FAISS + BM25 hybrid retrieval
  llm.py               Groq client with automatic model selection
  config.py            Settings
scripts/
  ocr.py               Resumable OCR
  build_index.py       Chunk, embed and index
static/
  index.html           Website page
  widget.js            Chat button and panel
  site.css             Website and widget styles
  chat.html            Full-page chat
data/                  Curated knowledge base
output/                Processed text, chunks and vector index
```

## Limitations

- Information reflects the data available when the index was built. Confirm fees, dates and notices with the college.
- OCR can occasionally misread words or numbers in scanned tables.
- Requires internet access for the language model.
- Hindi written in English letters (for example "hostel ki fees kitni hai") is treated as English.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Index not found" | Run `python scripts/build_index.py` |
| "Groq API key is missing or invalid" | Check `.env` is named exactly `.env`, the key has no spaces or quotes, then restart |
| Rate-limit message | Wait a minute and try again |
| Port already in use | Set `PORT=3001` in `.env` |
| Model error | Open `/api/models`, pick a listed model and set `GROQ_MODEL` |

## Contact

For college enquiries: 02563-259600 · director@rcpit.ac.in · https://www.rcpit.ac.in
