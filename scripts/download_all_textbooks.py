"""
Download English-edition King Sejong Institute / Sejong Korean textbooks to the book/ folder.
Source: https://github.com/coughingmouse/Download-Korean-Textbooks
"""
import os
import shutil
import tempfile
import requests
from fpdf import FPDF

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "book")
os.makedirs(OUTPUT_DIR, exist_ok=True)


class metadata:
    def __init__(self, name, iden, pages):
        self.name = name
        self.iden = iden
        self.pages = pages


book_ids = [
    # Practical Korean 1 & 2 (English)
    metadata("King Sejong Institute Practical Korean 1 English", 824, 182),
    metadata("King Sejong Institute Practical Korean 2 English", 825, 186),

    # Practical Korean 3 & 4 (Korean only, no English edition exists)
    metadata("King Sejong Institute Practical Korean 3", 831, 182),
    metadata("King Sejong Institute Practical Korean 4", 832, 182),

    # Introduction (English)
    metadata("King Sejong Institute Korean Introduction English", 906, 261),

    # Sejong Korean main textbooks (English editions)
    metadata("Sejong Korean 1A (ENGLISH EDITION)", 793, 142),
    metadata("EXTENSION ACTIVITY BOOK 1A (ENGLISH EDITION)", 797, 66),

    metadata("Sejong Korean 1B (ENGLISH EDITION)", 794, 138),
    metadata("EXTENSION ACTIVITY BOOK 1B (ENGLISH EDITION)", 798, 74),

    metadata("Sejong Korean 2A (ENGLISH EDITION)", 795, 138),
    metadata("EXTENSION ACTIVITY BOOK 2A (ENGLISH EDITION)", 799, 86),

    metadata("Sejong Korean 2B (ENGLISH EDITION)", 796, 138),
    metadata("EXTENSION ACTIVITY BOOK 2B (ENGLISH EDITION)", 800, 86),
]


def safe_filename(name: str) -> str:
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name


def get_img(image_url: str, filename: str) -> bool:
    try:
        r = requests.get(image_url, stream=True, timeout=30)
        if r.status_code == 200:
            r.raw.decode_content = True
            with open(filename, "wb") as f:
                shutil.copyfileobj(r.raw, f)
            return True
    except Exception as e:
        print(f"  Warning: could not fetch {image_url}: {e}")
    return False


def get_pdf(book: metadata):
    out_path = os.path.join(OUTPUT_DIR, safe_filename(book.name) + ".pdf")
    if os.path.exists(out_path):
        print(f"  Skipping (already exists): {book.name}", flush=True)
        return

    pdf = FPDF()
    failed_pages = []

    with tempfile.TemporaryDirectory(prefix=str(book.iden)) as tmpdir:
        for i in range(book.pages):
            num = str(i + 1).zfill(3)
            url = f"https://nuri.iksi.or.kr/e-book/catImage/{book.iden}/{num}.jpg"
            fname = os.path.join(tmpdir, f"{num}.jpg")
            ok = get_img(url, fname)
            if ok:
                pdf.add_page()
                pdf.image(fname, 0, 0, 210, 297)
                print(f"  Page {i+1}/{book.pages}", end="\r", flush=True)
            else:
                failed_pages.append(i + 1)

        if len(failed_pages) == book.pages:
            print(f"\n  FAILED (no pages retrieved) – skipping PDF write.", flush=True)
            return

        print(f"\n  Building PDF...", flush=True)
        pdf.output(out_path, "F")

    if failed_pages:
        print(f"  Done (missing pages: {failed_pages}): {book.name}", flush=True)
    else:
        print(f"  Done: {book.name}", flush=True)


def main():
    total = len(book_ids)
    for idx, book in enumerate(book_ids, 1):
        print(f"[{idx}/{total}] {book.name} ({book.pages} pages)", flush=True)
        get_pdf(book)
    print("\nAll done!", flush=True)


if __name__ == "__main__":
    main()
