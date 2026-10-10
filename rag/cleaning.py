"""Clean OCR text and turn it into page-aware chunks.

The PDF is a browser print-out of rcpit.ac.in, so every page has:
  header : "9/20/26, 5:36 PM <Page title>"
  footer : "https://www.rcpit.ac.in/<slug>   12/89"
We lift title + URL into metadata and drop repeated boilerplate lines.
"""
import collections
import re

HEADER_RE = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}\s*[AaPp][Mm]\s*(.*)$")
URL_RE = re.compile(r"https?://www\.rcpit\.ac\.in[^\s)\]]*", re.I)
URL_ONLY_RE = re.compile(r"^\s*(https?://www\.rcpit\.ac\.in\S*?)(?:\s+\d{1,4}\s*/\s*\d{1,4})?\s*$", re.I)
NAV_RE = re.compile(r"\(\s*https?\s*[:/]", re.I)
BARE_HOME = re.compile(r"^https?://www\.rcpit\.ac\.in/?$", re.I)
PAGENUM_RE = re.compile(r"^\s*\d{1,4}\s*/\s*\d{1,4}\s*$")
FOOTER_PAGENUM_TAIL = re.compile(r"\s+\d{1,4}\s*/\s*\d{1,4}\s*$")


def _is_nav_line(line):
    """Website menu entries such as 'ABOUT US (HTTPS:/WWW.RCPIT.AC.IN/ABOUT-US)'."""
    if not NAV_RE.search(line) or len(line) > 160:
        return False
    letters = [ch for ch in line if ch.isalpha()]
    return bool(letters) and sum(ch.isupper() for ch in letters) / len(letters) > 0.6


def _norm(line):
    return re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()


def find_boilerplate(pages, min_fraction=0.20):
    """Normalized multi-word lines that appear on >= min_fraction of pages."""
    df = collections.Counter()
    for p in pages:
        df.update({_norm(l) for l in p["text"].split("\n") if len(_norm(l)) >= 15})
    cutoff = max(8, int(len(pages) * min_fraction))
    return {k for k, v in df.items() if v >= cutoff}


def clean_pages(pages):
    """pages: list of {page, text, ...} -> list of {page, title, url, text}."""
    boiler = find_boilerplate(pages)
    out = []
    for p in pages:
        title, head_url, foot_url, kept = "", "", "", []
        lines = [l.strip() for l in p["text"].split("\n")]
        for i, line in enumerate(lines):
            if not line:
                continue
            m = HEADER_RE.match(line)
            if m and i < 4:
                title = title or m.group(1).strip()
                continue
            u = URL_ONLY_RE.match(line)
            if u and (i < 4 or i >= len(lines) - 4):
                found = u.group(1).rstrip(".,;")
                if i < 4:
                    head_url = head_url or found
                else:
                    foot_url = found  # last one wins: the browser footer
                continue
            if BARE_HOME.match(line.strip("()» ")):
                continue  # site-logo link
            if PAGENUM_RE.match(line):
                continue
            n = _norm(line)
            if len(n) < 2 or n in boiler or _is_nav_line(line):
                continue
            kept.append(line)
        # the footer URL is the real page address; the header one is often just the logo link
        url = foot_url or ("" if BARE_HOME.match(head_url) else head_url)
        text = "\n".join(kept)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        out.append({"page": p["page"], "title": title, "url": url, "text": text})
    return out


def _title_from_url(url):
    slug = url.rstrip("/").split("/")[-1] if url else ""
    return slug.replace("-", " ").replace("_", " ").title()


def _same_doc(cur, p):
    if cur["url"] and p["url"]:
        return cur["url"] == p["url"]
    t1, t2 = _norm(cur["title"]), _norm(p["title"])
    return not t1 or not t2 or t1 == t2


def group_pages(cleaned):
    """Consecutive pages that belong to the same web page are grouped together
    (same footer URL, or same header title when the URL was not readable)."""
    groups, cur = [], None
    for p in cleaned:
        if cur is None or not _same_doc(cur, p):
            cur = {"url": p["url"], "title": p["title"], "pages": []}
            groups.append(cur)
        else:
            cur["url"] = cur["url"] or p["url"]
            cur["title"] = cur["title"] or p["title"]
        cur["pages"].append(p)
    for g in groups:
        g["title"] = g["title"] or _title_from_url(g["url"]) or "RCPIT"
    return groups


def chunk_groups(groups, chunk_words=350, overlap=60, min_words=25):
    """Sliding word window inside each group; every word remembers its page."""
    chunks = []
    for g in groups:
        words, wpages = [], []
        for p in g["pages"]:
            w = p["text"].split()
            words += w
            wpages += [p["page"]] * len(w)
        if not words:
            continue
        step = max(1, chunk_words - overlap)
        start = 0
        while start < len(words):
            end = min(len(words), start + chunk_words)
            # avoid a tiny tail chunk: absorb it into this one
            if len(words) - end < min_words:
                end = len(words)
            body = " ".join(words[start:end])
            pgs = sorted(set(wpages[start:end]))
            if len(body.split()) >= min_words or not chunks:
                chunks.append({
                    "id": len(chunks),
                    "title": g["title"],
                    "url": g["url"],
                    "page_start": pgs[0],
                    "page_end": pgs[-1],
                    "text": body,
                })
            if end >= len(words):
                break
            start += step
    return chunks


HEADING_RE = re.compile(r"^[^-|\s].{6,70}:\s*$")


def knowledge_chunks(pdf_path, chunk_words=350, overlap=60):
    """Curated knowledge base PDF -> one chunk group per ALL-CAPS section heading."""
    import pymupdf
    doc = pymupdf.open(str(pdf_path))
    sections, cur = [], {"title": "Overview", "lines": [], "page": 1}
    for pno, page in enumerate(doc, 1):
        for line in page.get_text().split("\n"):
            line = line.strip()
            if not line:
                continue
            letters = [c for c in line if c.isalpha()]
            if (HEADING_RE.match(line) and letters
                    and sum(c.isupper() for c in letters) / len(letters) > 0.6):
                if cur["lines"]:
                    sections.append(cur)
                cur = {"title": line.rstrip(":"),
                       "lines": [], "page": pno}
            else:
                cur["lines"].append(line)
    if cur["lines"]:
        sections.append(cur)
    out = []
    for sec in sections:
        if sec["title"].upper() in ("ANSWERING POLICY", "OVERVIEW"):
            continue  # meta text, not facts (the policy lives in the system prompt)
        title = f"Knowledge Base - {sec['title'].title()}"
        group = {"title": title, "url": "https://www.rcpit.ac.in/",
                 "pages": [{"page": sec["page"], "text": "\n".join(sec["lines"])}]}
        for c in chunk_groups([group], chunk_words, overlap, min_words=1):
            c["kind"] = "knowledge"
            out.append(c)
    return out
