"""Flask server: retrieval (FAISS + BM25) -> Groq Llama -> answer + PDF page sources."""
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

from rag import config, llm
from rag.retriever import Retriever

app = Flask(__name__, static_folder="static", static_url_path="")

SYSTEM_PROMPT = """You are the enquiry assistant for R. C. Patel Institute of Technology (RCPIT), Shirpur, Maharashtra.
Answer the student's or parent's question using ONLY the CONTEXT provided with the question.

Rules:
- If the context does not contain the answer, say you could not find it in the available RCPIT information and suggest contacting the college (phone 02563-259600, email director@rcpit.ac.in, website https://www.rcpit.ac.in). Never invent facts.
- The context was extracted from scanned pages by OCR, so it may contain typos or broken tables. Be careful with numbers (fees, packages, dates, phone numbers); if a figure looks unclear, say so instead of guessing.
- Be concise and well organised. Use short bullet points for lists. Reply in the language of the question.
- Sources titled "Knowledge Base" are curated and reliable: prefer them for fees, seats, contacts and headline placement numbers, and use scanned PDF pages for detail.
- For fees always mention they are for 2025-26 and advise confirming from the official notice. For cutoffs, explain they vary by round, category and branch. For live deadlines or notices, point to rcpit.ac.in.
- Cite scanned PDF pages like [p. 12] or [pp. 40-42] at the end of the relevant sentence."""

_retriever = None
_lock = threading.Lock()
sessions = {}
SESSION_TTL = 2 * 60 * 60


def get_retriever():
    global _retriever
    with _lock:
        if _retriever is None:
            _retriever = Retriever()
        return _retriever


def pages_label(c):
    if c.get("kind") == "knowledge":
        return "curated info"
    return f"p. {c['page_start']}" if c["page_start"] == c["page_end"] else f"pp. {c['page_start']}-{c['page_end']}"


def build_context(chunks):
    parts = []
    for i, c in enumerate(chunks, 1):
        where = "curated knowledge base" if c.get("kind") == "knowledge" else f"PDF {pages_label(c)}"
        parts.append(f"[Source {i}: {c['title']}, {where}]\n{c['text']}")
    return "\n\n---\n\n".join(parts)


def retrieval_query(history, question):
    """Short follow-ups ('and the fees?') are expanded with the previous user question."""
    if len(question.split()) < 6:
        prev = [m["content"] for m in history if m["role"] == "user"]
        if prev:
            return f"{prev[-1]} {question}"
    return question


def cleanup_sessions():
    now = time.time()
    for sid in [s for s, v in sessions.items() if now - v["last"] > SESSION_TTL]:
        sessions.pop(sid, None)


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    sid, question = data.get("sessionId"), (data.get("message") or "").strip()
    if not sid or not question:
        return jsonify(error="sessionId and message are required."), 400
    cleanup_sessions()
    sess = sessions.setdefault(sid, {"messages": [], "last": time.time()})
    sess["last"] = time.time()
    history = sess["messages"][-config.HISTORY_MESSAGES:]

    try:
        chunks = get_retriever().search(retrieval_query(history, question))
    except FileNotFoundError as e:
        return jsonify(error=str(e)), 503
    except Exception as e:
        app.logger.exception("retrieval failed")
        return jsonify(error=f"Search failed: {e}"), 500

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": f"CONTEXT:\n{build_context(chunks)}\n\nQUESTION: {question}"}]
    try:
        reply = llm.chat(messages)
    except llm.GroqError as e:
        friendly = {401: "Groq API key is missing or invalid. Check GROQ_API_KEY in .env.",
                    429: "Groq rate limit reached - please wait a moment and try again."}.get(e.status, str(e))
        return jsonify(error=friendly), 502 if e.status >= 500 else e.status
    except Exception as e:
        app.logger.exception("llm failed")
        return jsonify(error=f"Could not reach Groq: {e}"), 502

    sess["messages"] += [{"role": "user", "content": question}, {"role": "assistant", "content": reply}]
    seen, sources = set(), []
    for c in chunks:
        key = (c["title"], c["page_start"], c["page_end"])
        if key not in seen:
            seen.add(key)
            sources.append({"title": c["title"], "pages": pages_label(c), "url": c["url"],
                            "page_start": c["page_start"]})
    return jsonify(reply=reply, sources=sources, sessionId=sid)


@app.delete("/api/chat/<sid>")
def clear(sid):
    sessions.pop(sid, None)
    return jsonify(success=True)


@app.get("/api/suggestions")
def suggestions():
    return jsonify(suggestions=[
        "🎓 What courses does RCPIT offer?",
        "💰 What is the fee structure?",
        "📋 How do I apply for admission?",
        "🏢 Which companies come for placements?",
        "🏠 Is hostel available?",
        "📊 What is the highest package at RCPIT?",
        "🔬 Does RCPIT have research facilities?",
        "📞 What is the RCPIT contact number?",
    ])


@app.get("/api/health")
def health():
    ready = _retriever is not None
    return jsonify(status="ok", index_loaded=ready,
                   chunks=len(_retriever.chunks) if ready else None,
                   embed_model=_retriever.model_name if ready else config.EMBED_MODEL,
                   groq_key_set=bool(config.GROQ_API_KEY), sessions=len(sessions))


@app.get("/api/models")
def models():
    """Which Groq models are currently available (handy when a model is deprecated)."""
    try:
        return jsonify(configured=config.GROQ_MODEL or None, available=llm.list_models(),
                       would_use=llm.resolve_model())
    except llm.GroqError as e:
        return jsonify(error=str(e)), e.status


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    try:
        get_retriever()
        print(f"Index loaded: {len(_retriever.chunks)} chunks")
    except Exception as e:
        print(f"WARNING: {e}")
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
