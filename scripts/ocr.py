"""
Smart, resumable OCR for the RCPIT PDF.

  - Page already has selectable text (>= MIN_CHARS)  -> use it, no OCR
  - Otherwise render the page and run Tesseract
  - Every finished page is appended to output/ocr_progress.jsonl immediately,
    so a crash / shutdown loses at most the pages in flight.
  - Re-running continues from where it stopped (resume is the default).

Usage:
    python scripts/ocr.py                  # resume (or start) OCR
    python scripts/ocr.py --resume         # same, explicit
    python scripts/ocr.py --restart        # throw away progress, start over
    python scripts/ocr.py --workers 4 --dpi 200
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rag import config  # noqa: E402

_doc = None


def _init_worker(pdf_path):
    global _doc
    import pymupdf
    if config.TESSERACT_CMD:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD
    _doc = pymupdf.open(pdf_path)


def _process_page(args):
    page_no, dpi, min_chars, lang, psm = args  # page_no is 1-based
    import pymupdf
    import pytesseract
    from PIL import Image
    try:
        page = _doc[page_no - 1]
        text = page.get_text().strip()
        if len(text) >= min_chars:
            return {"page": page_no, "method": "text", "text": text}
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        text = pytesseract.image_to_string(
            img, lang=lang, config=f"--oem 1 --psm {psm}"
        ).strip()
        return {"page": page_no, "method": "ocr", "text": text}
    except Exception as e:  # keep going; page can be retried on next run
        return {"page": page_no, "method": "error", "text": "", "error": str(e)}


def load_progress(path):
    done = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue  # half-written last line after a crash
                if rec.get("method") != "error":
                    done[rec["page"]] = rec
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(config.PDF_PATH))
    ap.add_argument("--dpi", type=int, default=config.OCR_DPI)
    ap.add_argument("--workers", type=int, default=config.OCR_WORKERS)
    ap.add_argument("--min-chars", type=int, default=config.MIN_TEXT_CHARS)
    ap.add_argument("--lang", default=config.OCR_LANG)
    ap.add_argument("--psm", type=int, default=3)
    ap.add_argument("--resume", action="store_true", help="(default) continue previous run")
    ap.add_argument("--restart", action="store_true", help="discard progress and start over")
    args = ap.parse_args()

    import pymupdf
    pdf = Path(args.pdf)
    if not pdf.exists():
        sys.exit(f"PDF not found: {pdf}\nPut it at data/Merged_data.pdf or pass --pdf PATH")

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    progress_file = config.OUTPUT_DIR / "ocr_progress.jsonl"
    if args.restart and progress_file.exists():
        progress_file.unlink()

    total = len(pymupdf.open(str(pdf)))
    done = load_progress(progress_file)
    todo = [p for p in range(1, total + 1) if p not in done]
    print(f"PDF: {pdf.name}  pages={total}  already done={len(done)}  remaining={len(todo)}")

    if todo:
        jobs = [(p, args.dpi, args.min_chars, args.lang, args.psm) for p in todo]
        t0 = time.time()
        n = 0
        with open(progress_file, "a", encoding="utf-8") as out, \
                mp.Pool(args.workers, _init_worker, (str(pdf),)) as pool:
            try:
                for rec in pool.imap_unordered(_process_page, jobs, chunksize=1):
                    if rec["method"] == "error":
                        print(f"  page {rec['page']} FAILED: {rec.get('error')}")
                        continue
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out.flush()
                    os.fsync(out.fileno())
                    done[rec["page"]] = rec
                    n += 1
                    if n % 10 == 0 or len(done) == total:
                        rate = n / (time.time() - t0)
                        eta = (total - len(done)) / rate / 60 if rate else 0
                        print(f"Page {len(done)}/{total} ✓  ({rate:.2f} pg/s, ~{eta:.0f} min left)", flush=True)
            except KeyboardInterrupt:
                pool.terminate()
                print("\nInterrupted — progress saved. Re-run to resume.")
                sys.exit(1)

    missing = [p for p in range(1, total + 1) if p not in done]
    if missing:
        print(f"{len(missing)} pages failed: {missing[:20]}... — re-run to retry them.")
        sys.exit(2)

    pages = [done[p] for p in range(1, total + 1)]
    for r in pages:
        r["chars"] = len(r["text"])
    with open(config.OCR_PAGES_JSON, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False)
    ocr_n = sum(r["method"] == "ocr" for r in pages)
    print(f"Done. {total} pages ({ocr_n} OCR, {total - ocr_n} text layer) -> {config.OCR_PAGES_JSON}")


if __name__ == "__main__":
    main()
